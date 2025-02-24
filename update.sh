#!/usr/bin/env bash
terraform apply
terraform output -json > terraform.out

export ANSIBLE_CONFIG=./ansible.cfg

jinja2 --format=json ansible_inventory.j2 terraform.out > ansible_inventory
ansible-playbook -i ansible_inventory reverse_proxy.yml
ansible-playbook -i ansible_inventory clickhouse.yml
ansible-playbook -i ansible_inventory compute.yml
