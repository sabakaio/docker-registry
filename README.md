# Docker Registry

Docker Registry AWS setup automation.

## Installation

- Create *Elastic IP* and add DNS record to this IP. We need this configured to issue sertificates using *LetsEncrypt*.
- Create a DNS record for the Registry to point to *Elastic IP* created in previous step
- Generate *CloudFormation* template using *troposphere* `python troposphere/registry.py > registry.template`
- Create a *CloudFormation Stack* using `registry.template`

## TODO

- Copy certs after renewal and restart Registry
- CloudFormation wait condition for registry instance
