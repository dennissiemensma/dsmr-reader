# DSMR Reader #

Installation instructions are based on the Raspbian distro for RaspberryPi, but it should generally work on every Debian based system, as long as the dependencies & requirements are met.

## Usage ##
There are plenty of 'scripts' available online for performing DSMR readings. This project however is a full stack solution. This allows a decent implentation of most features, but requires a certain 'skill' as you will need to install several dependencies. 
I advise you to only use this tool when you have basic Linux knowledge or interest in the components used.

## Dependencies & requirements ##
* RaspberryPi 2 *(minimal v1 B required but v2 is recommended)*.
* Raspbian *(or Debian based distro)*.
* Python 3.4+.
* Smart Meter with support for at least DSMR 4.0 *(i.e. Landis + Gyr E350 DSMR4)*.
* Minimal of 100 MB disk space on RaspberryPi *(for application & virtualenv)*. More disk space is required for storing all reader data captured *(optional)*.
* Smart meter P1 data cable *(can be purchased online and they cost about 20 Euro's each)*.
* Basic Linux knowledge for deployment, debugging and troubleshooting. 

## Installation guide #
The installation will take about an hour, but it also depends on your Linux skills and whether you need to understand every bit of information described in the guide.

You should already have an OS running on your RaspberryPi. Here is a brief hint for getting things started. Skip the OS chapter below if you already have your RaspberryPi up and running.

### Operating System Installation (optional) ###
#### Raspbian ####
Either use the headless version of Raspbian, [netinstall](https://github.com/debian-pi/raspbian-ua-netinst), or the [full Raspbian image](https://www.raspbian.org/RaspbianImages), with graphics stack. You don't need the latter when you intend to only use your decive for DSMR readings.

#### Init ####
Power on RaspberryPi and connect using SSH:

`ssh pi@IP-address` (full image)

or

`ssh root@IP-address` (headless)


##### IPv6 #####
Disable IPv6 if you get timeouts or other weird networking stuff related to IPv6.

```
echo "net.ipv6.conf.all.disable_ipv6 = 1" >> /etc/sysctl.conf

sysctl -p /etc/sysctl.conf
```

##### Sudo #####
Make sure you are up to date:
`apt-get install sudo`  *(headless only)*

##### Updates #####
```
sudo apt-get update

sudo apt-get upgrade
```


##### raspi-config #####
Install this RaspberryPi utility.

`sudo apt-get install raspi-config`

Now run it: `raspi-config`. You should see a menu containing around ten options to choose from.

Make sure to enter the menu **5. Internationalisation Options** and set timezone *(I2)* to UTC. This is required to prevent any bugs resulting from the DST transition twice every year. It's also best practice for your database backend anyway.

You should also install any locales you require. Go to **5. Internationalisation Options** and select *I1*. You probably need at least English and Dutch locales: **en_US.UTF-8 UTF-8** + **nl_NL.UTF-8 UTF-8**. You can select multiple by pressing the spacebar and finish with TAB + Enter.

* If your sdcard/disk space is not yet fully utilized, select **#1 Expand Filesystem**.
* If you do not have a RaspberryPi 2, you might want to select **#8 Overclock** *(setting MODEST, 0 overvolt!)* 

If the utility asks you whether to reboot, choose yes to reflect the changes you made.

##### Extra's #####
Running the headless Raspbian netinstall? You might like Bash completion. Check [this article](https://www.howtoforge.com/how-to-add-bash-completion-in-debian) how to do this.

Running the full Rasbian install? You should check whether you require the [Wolfram Engine](http://www.wolfram.com/raspberry-pi/), which is installed by default, but takes about a whopping 500 MB disk space! Run `sudo apt-get purge wolfram-engine` if you don't need it.

----

### Application Installation ### 
Make sure you have your system running in UTC timezone to prevent weird DST bugs.

#### Database backend ####
The application stores by default all readings taken from the serial cable. Depending on your needs, you can choose for either (option A.) **MySQL/MariaDB** or (option B.) **PostgreSQL**. If you have no idea what to choose, I generally advise to pick MySQL/MariaDB, as it's less complex as PostgreSQL and is easier to learn. For a project of this size and complexity it doesn't matter anyway. :]


##### (Option A.) MySQL/MariaDB ####
Install MariaDB. You can also choose to install the closed source MySQL, as they should be interchangeable anyway. **libmysqlclient-dev** is required for the virtualenv installation later in this guide..

`sudo apt-get install mariadb-server-10.0 libmysqlclient-dev` 

Create database:

`sudo mysqladmin create dsmrreader`

Create user:

`echo "CREATE USER 'dsmrreader'@'localhost' IDENTIFIED BY 'dsmrreader';" | sudo mysql --defaults-file=/etc/mysql/debian.cnf -v`

Set privileges for user:

`echo "GRANT ALL ON dsmrreader.* TO 'dsmrreader'@'localhost';" | sudo mysql --defaults-file=/etc/mysql/debian.cnf -v`

Flush privileges to activate them:

`mysqladmin reload`

##### (Option B.) PostgreSQL

Install PostgreSQL. **postgresql-server-dev-all** is required for the virtualenv installation later in this guide.

`sudo apt-get install postgresql postgresql-server-dev-all`

Postgres does not start due to locales? Try: `dpkg-reconfigure locales`

No luck? Try editing `/etc/environment`, add `LC\_ALL="en_US.utf-8"` and `reboot`

Ignore any *'could not change directory to "/root": Permission denied'* errors for the following commands.

Create user:

`sudo sudo -u postgres createuser -DSR dsmrreader`

Create database, owned by the user we just created:

`sudo sudo -u postgres createdb -O dsmrreader dsmrreader`

Set password for user:

`sudo sudo -u postgres psql -c "alter user dsmrreader with password 'dsmrreader';"`


#### Dependencies ####
Misc utils, required for webserver, application server and cloning the application code from the repository.

`sudo apt-get install nginx supervisor mercurial python3 python3-pip python3-virtualenv virtualenvwrapper`

Install `cu`. The CU program allows easy testing for your DSMR serial connection. It's very basic but very effective to test whether your serial cable setup works properly.

`sudo apt-get install cu`


#### Application user ####
The application runs as `dsmr` user by default. This way we do not have to run the application as `root`, which is a bad practice anyway. Our user also requires dialout permissions.

Create user with homedir. The application code and virtualenv resides in this directory as well:

`sudo useradd dsmr --home-dir /home/dsmr --create-home --shell /bin/bash`

Allow the user to perform a dialout.

`sudo usermod -a -G dialout dsmr`


### Webserver (Nginx) ###
We will now prepare the webserver, Nginx. It will serve all application's static files directly and proxy application requests to the backend, Supervisor, which we will configure later on.

Django will copy all static files to a separate directory, used by Nginx to serve statics. 

`sudo mkdir -p /var/www/dsmrreader/static`

`sudo chown -R dsmr:dsmr /var/www/dsmrreader/`

### This first reading ###

Now login as the user we just created, to perform our very first reading!

`sudo su - dsmr`

Test with **cu** (BAUD rate settings for *DSMR v4* is **115200**, for older verions it should be **9600**). 

`cu -l /dev/ttyUSB0 -s 115200 --parity=none`

You now should see something like 'Connected.' and a wall of text and numbers within 10 seconds. Nothing? Try different BAUD rate, as mentioned above. You might also check out a useful blog, such as [this one (Dutch)](http://gejanssen.com/howto/Slimme-meter-uitlezen/).


### Application code clone ###
Now is the time to clone the code from the repository and check it out on your device. Make sure you are still logged in as our **dsmr** user:

`sudo su - dsmr`

`hg clone https://bitbucket.org/dennissiemensma/dsmr-reader`


### Virtualenv ###

The dependencies our application uses are stored in a separate environment, also called **VirtualEnv**. Although it's just a folder inside our user homedir, it's very effective as it allows us to keep dependencies isolated and also run different versions on the same machine. More info can be found [here](http://docs.python-guide.org/en/latest/dev/virtualenvs/).

`sudo su - dsmr`

Create folder for the virtualenvs of this user:

`mkdir ~/.virtualenvs`

Create a new virtualenv, we usually use the same name for it as the application or project. It's important to specify python3 as the default intepreter: 

`virtualenv ~/.virtualenvs/dsmrreader --no-site-packages --python python3`

Now 'activate' the environment. It effectively points all aliases for software installed in the virtualenv to the binaries inside the virtualenv. I.e. the Python binary inside `/usr/bin/python` won't be used when the virtualenv is activated, but `/home/dsmr/.virtualenvs/dsmrreader/bin/python` instead will.

Activate & cd to project:

```
source ~/.virtualenvs/dsmrreader/bin/activate

cd ~/dsmr-reader
```

You might want to put the 'source' command above in the user's `~/.bashrc` (logout and login to test). I also advice to put the `cd ~/dsmr-reader` in there as well, which will cd you directly inside the project folder on login.


### Application settings & init ###
Earlier in this guide you had to choose for either (A.) MySQL/MariaDB or (B.) PostgreSQL. Our applications needs to know what backend to talk to. Therefor I created two default configuration files you can copy. 
The application will also need the appropiate database client, which is not installed by default. Again I created two ready-to-use requirements file, which will also install all other dependencies required, such as the Django framework. Installation might take a while, depending on your Internet connection and hardware. Nothing to worry about. :]

A. Did you choose MySQL/MariaDB? Execute these two commands:

```
cp dsmrreader/provisioning/django/mysql.py dsmrreader/settings.py

pip3 install -r dsmrreader/provisioning/requirements/base.txt -r dsmrreader/provisioning/requirements/mysql.txt
```

B. Or did you choose MySQL/MariaDB? Then execute these two lines:

```
cp dsmrreader/provisioning/django/postgresql.py dsmrreader/settings.py

pip3 install -r dsmrreader/provisioning/requirements/base.txt -r dsmrreader/provisioning/requirements/postgresql.txt
```

Did every go as planned? When either of the database clients refures to install due to missing files/configs, make sure you installed `libmysqlclient-dev` (MySQL) or `postgresql-server-dev-all` (PostgreSQL) earlier in the process, when you installed the database server itself.

Now it's time to bootstrap the application and check whether all settings are good and requirements are met. Execute this to init the database:
 
`./manage.py migrate`

Prepare static files for webinterface. This will copy all statis to the directory we created for Nginx earlier:

`./manage.py collectstatic --noinput`

Create an application superuser. Django will prompt you for a password. Alter username and email when you feel you need to, but email is not (yet) used in the application anyway. The credentials generated can be used to access the administration panel inside the application, which requires authentication.

`./manage.py createsuperuser --username admin --email root@localhost`

**OPTIONAL**: The application will run without your energy prices, but if you want some sensible defaults (actually my own energy prices for a brief period). Altering prices later won't affect your data, because prices are calculated retroactive anyway. 

`./manage.py loaddata dsmr_stats/fixtures/EnergySupplierPrice.json` 

### Webserver (Nginx) part 2 ### 
Now to back to root/sudo-user to config webserver. Remove the default vhost (if you didn't use it yourself anyway!).

`sudo rm /etc/nginx/sites-enabled/default`

Copy application vhost, it will listen to **any** hostname (wildcard), but you may change that if you feel like you need to. It won't affect the application anyway.

`sudo cp /home/dsmr/dsmr-reader/dsmrreader/provisioning/nginx/dsmr-webinterface /etc/nginx/sites-enabled/`

Let Nginx verify vhost syntax and reload Nginx when configtest passes.

```
sudo service nginx configtest

sudo service nginx reload
```


### Supervisor. ###
Now we configure [Supervisor](http://supervisord.org/), which is used to run our application and also all background jobs. Each job has it's own configuration file, so make sure to copy them all:  

`sudo cp /home/dsmr/dsmr-reader/dsmrreader/provisioning/supervisor/dsmr_*.conf /etc/supervisor/conf.d/`

**NOTE**: `dsmr\_stats\_poller.conf` is LEGACY and should be skipped/removed!

`rm /etc/supervisor/conf.d/dsmr_stats_poller.conf`

Login to supervisor management console:

`sudo supervisorctl`

Enter these commands (after the >). It will force Supervisor to check its config directory and use/reload the files.

> supervisor> `reread`

> supervisor> `update`

Three processed should be started or running. Make sure they don't end up in **ERROR** state, so refresh with 'status' a few times. `dsmr\_stats\_compactor` and `dsmr\_stats\_datalogger` will restart every time. This is intended behaviour. `dsmr\_webinterface` however should keep running.  
> supervisor> `status`

Example of everything running well:

<pre>dsmr_stats_compactor             STARTING</pre>
<pre>dsmr_stats_datalogger            RUNNING</pre>
<pre>dsmr_webinterface                RUNNING</pre>
 
Want to check whether data logger works? Just tail log in supervisor with:

> supervisor> `tail -f dsmr\_stats\_datalogger`

You should see similar output as the CU-command used earlier on the command line.
Want to quit supervisor? `CTRL + C` to stop tail and `CTRL + D` once to exit supervisor command line.

Everything OK? Congratulations, this was the hardest part and now the fun begins! :]

You might want to `reboot` and check whether everything comes up automatically again with `sudo supervisorctl status`. This will make sure your data logger 'survives' any power surges.

### Public webinterface warning ###
**NOTE**: Running production and *public*? Please make sure to ALTER the `SECRET_KEY` setting in your `settings.py`