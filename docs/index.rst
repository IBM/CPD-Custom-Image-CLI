.. custom-image-cli documentation master file, created by
   sphinx-quickstart on Fri Jul 29 09:57:05 2022.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Custom Image CLI for Runtimes in Cloud Pak for Data 
====================================

************************************************************************
CLI to create and use custom image runtimes
************************************************************************

This project streamlines the process of creating a custom image for Cloud Pak for Data runtimes by wrapping the key steps into CLI commands, covering:
1. gather the needed information such as base image names
2. build one custom image per base image, in batch
3. push each custom image to a target container registry
4. register a custom image with the corresponding Cloud Pak for Data service

Currently it supports the following services:

#. Watson Studio
  * Jupyter notebook and Jupyter Lab environments in Python
  * Rstudio environments

The support for Watson Machine Learning is not fully implemented but should be there soon. Stay tunned!

Important notes
###############

1 - The current release is implemented and tested only for Cloud Pak for Data **4.0.x**. If you are on 3.5.x, it does not apply because the way to fetch base images is changed in 4.0.x. If you are on 4.5.x, this CLI may work.

2 - Gathering information and registering custom images are specific to Cloud Pak for Data, while building and pushing the custom image can be easily extended to support arbitrary situation.

3 - You need to know the key to access the Cloud Pak for Data base image repository (**cp.icr.io**), or have access to the OpenShift backend of any 4.0.x Cloud Pak for Data cluster you are building a custom image for from where you will be able to extract the secrets according to the :doc:`Getting Started Guide <getting_started>` in this doc.

4 - R Jupyter environment is not tested or supported by this CLI as usually R users prefer Rstudio. Contact the author if there is a need.

More Links
###############
* Watson Studio Doc: https://www.ibm.com/docs/en/cloud-paks/cp-data/4.0?topic=environments-building-custom-images
* Watson Machine Learning Doc: https://www.ibm.com/docs/en/cloud-paks/cp-data/4.0?topic=functions-working-custom-images


.. toctree::
   :maxdepth: 1
   :caption: Contents

   Getting started: Watson Studio <getting_started>
   Retrieve or Register Container Registry Secrets <cluster_secrets>
   
.. toctree::
   :maxdepth: 1
   :caption: Quick Examples

   Cheat Sheet <cheat_sheet>

