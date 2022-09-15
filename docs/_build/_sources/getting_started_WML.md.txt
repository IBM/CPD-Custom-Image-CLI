# Getting Started: Create Custom Images for Watson Machine Learning (Cloud Pak for Data)

If you are already familiar with how to use the tool for Watson Studio custom images, here with Watson Machine Learning the only differences are:
- list base images: use arg `--service wml`
- build and/or push custom images: same
- register in Cloud Pak for Data: a slightly different set of arguments to use, for example
```
python cli_ws_image.py custom register --service wml --storage-volume cpd-instance::cc-home-pvc-sv -s runtime22.1-py3.9 -ss custom-452-software-spec-{image_name}.json -r custom-452-{filename} -d "{display_name} (custom)" -i us.icr.io/cpd-custom-image/{image_name}-custom:4.5.2 -v 4.5.2 --dry-run
```
  - `--storage-volume`: storage volume display name from where we read and write software spec files 
  - `--base-software-spec` or `-s`: the base software spec to use as template, if not specified it will try to determine the base one automatically and sometimes runs into error because of the custom ones you put in that confuses the logic
  - `--software-spec-pattern` or `-ss`: filename pattern for software spec where the original software spec filename can be referred as `{filename}` and the extracted base image name can be referred as `{image_name}`; it's recommended to specify `{image_name}` in the pattern if you are dealing with a batch of available custom images (e.g., py3.6, py3.7, py3.8 altogether) because in this case the original software spec is no longer distinctive as you may use one for all of them, while the extracted base image name will stay unique

