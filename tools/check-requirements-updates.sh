#!/usr/bin/env bash

# Clean start.
rm -f /tmp/outdated.txt /tmp/outdated-reqs.txt /tmp/reqs.txt

# Keep pip in sync with reqs
echo "Installing pinned requirements"
pip3 install -r dsmrreader/provisioning/requirements/base.txt -r dsmrreader/provisioning/requirements/dev.txt

# List outdated packages
echo "Checking for outdated packages"
pip list --outdated --local --format freeze | tr '[:upper:]' '[:lower:]' | cut -d'=' -f1 | sort > /tmp/outdated.txt

# List packages from requirements
cat dsmrreader/provisioning/requirements/*.txt | tr '[:upper:]' '[:lower:]' | grep -v '#' | grep -v '.txt' | cut -d'=' -f1 | sort > /tmp/reqs.txt

# Find outdated packages from requirements
comm -1 -2 /tmp/outdated.txt /tmp/reqs.txt > /tmp/outdated-reqs.txt


echo "Refreshing for outdated packages"
pip list --outdated --local

echo ""
echo "The following project requirements are outdated:"
echo "------------------------------------------------"
echo ""

cat /tmp/outdated-reqs.txt
echo ""
