# Docker Registry

Docker Registry AWS setup automation.

## The Stack

A *ClouudFormation* template `registry.template` is going to create a *EC2 Instance* to host *Docker Registry* App and *S3 Bucket* to store images.
An *EC2 Instance* image ID will be choosen automatically for a given region using the autolookup function ([Looking Up Amazon Machine Image IDs](http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/walkthrough-custom-resources-lambda-lookup-amiids.html)).

## Installation

Login to *AWS Console*, go to *CloudFormation* service page, ensure your current region. Then create a new stack using `registry.template`.
