#!/bin/sh
script/setup
pip3 install -r requirements_test_all.txt -c homeassistant/package_constraints.txt
