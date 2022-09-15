# Cheat Sheet

## 0. Preparation: specify if not in watson studio
```bash
export CPD_BASE_URL=******
export CPD_USERNAME=******
export CPD_APIKEY=******
```

## 1. Get base image names
### latest cpd version
```bash
python cli_ws_image.py default list --cpu
python cli_ws_image.py default list --gpu
python cli_ws_image.py default list -a
python cli_ws_image.py default list --rstudio

# specify service
python cli_ws_image.py default list --service ws --cpu # default service is ws
python cli_ws_image.py default list --service wml --cpu

# export
python cli_ws_image.py default list --cpu --export-fn base_images_nongpu_451.txt
python cli_ws_image.py default list --rstudio --export-fn base_images_rstudio_451.txt -o
```

### historical cpd version: use --cpd-version arg
```bash
python cli_ws_image.py default list -a --cpd-version 4.0.6

python cli_ws_image.py default list --rstudio --cpd-version 4.0.7 --export-fn base_images_rstudio_407.txt

python cli_ws_image.py default list --service wml --cpu --cpd-version 4.0.7 --export-fn base_images_wmlpython_407.txt
```

## 2. Build custom images
Login to docker:
```bash
docker login cp.icr.io --username <username> --password <password>
```
Then run the commands:
```bash
python cli_ws_image.py custom build --dir-dockerfile ../custom-image --base-image-list base_images_nongpu_408.txt --custom-image-name-pattern {image_name}-ws-applications

python cli_ws_image.py custom build --dir-dockerfile . --base-image-list base_images_wmlpython_407.txt --custom-image-name-pattern {image_name}-custom
```

## 3. Push custom images
Login to docker:
```bash
# in general
docker login <registry-url-for-custom-images> --username <username> -- password <password>

# ibmcloud container registry
ibmcloud login -g <resource-group> --apikey <apikey> && ibmcloud cr login

# CPD internal registry: you may need to address the insecure registry problem (https://docs.docker.com/registry/insecure/)
docker login -u $(oc whoami) -p $(oc whoami -t) default-route-openshift-image-registry.****
```
Then run the commands:
```bash
# push using info from base image list, easy for pushing custom images based on multiple base images
python cli_ws_image.py custom push --base-image-list ./base_images_wmlpython_408.txt --custom-image-name-pattern {image_name}-custom --registry-url us.icr.io --registry-namespace cpd-custom-image

# push using image name
python cli_ws_image.py custom push --image-name wml-deployment-runtime-py39-1-custom --custom-image-name-pattern {image_name}-custom --registry-url us.icr.io --registry-namespace cpd-custom-image
```

## 2+3 - Build & Push in one command: use flag --push and other args needed by the push command
```bash
python cli_ws_image.py custom build --dir-dockerfile . --base-image-list base_images_wmlpython_407.txt --custom-image-name-pattern {image_name}-custom --push --registry-url us.icr.io --registry-namespace cpd-custom-image
```

## 3. Register custom images in watson studio
Remove `--dry-run` flag to allow the file to be put into the correct location in CPD.
```bash
python cli_ws_image.py custom register --jupyter --dry-run
python cli_ws_image.py custom register --jupyterlab --dry-run
python cli_ws_image.py custom register --jupyter-all --dry-run
python cli_ws_image.py custom register --jupyter-all -py 3.8 -v 4.0.6 --dry-run

python cli_ws_image.py custom register --jupyter-all -r ws-applications-408-{filename} -d "{display_name} (ws applications)" -i us.icr.io/custom-image-ws-applications/{image_name}-ws-applications:4.0.8 -v 4.0.8 --dry-run
python cli_ws_image.py custom register --gpu --jupyter-all -r ws-applications-408-{filename} -d "{display_name} (ws applications)" -i us.icr.io/custom-image-ws-applications/{image_name}-ws-applications:4.0.8 -v 4.0.8 --dry-run

python cli_ws_image.py custom register --service wml --storage-volume cpd-instance::cc-home-pvc-sv -s runtime22.1-py3.9 -ss custom-452-software-spec-{image_name}.json -r custom-452-{filename} -d "{display_name} (custom)" -i us.icr.io/cpd-custom-image/{image_name}-custom:4.5.2 -v 4.5.2 --dry-run
```

## 4. Other commnds
### 4.1 list custom configs
```bash
python cli_ws_image.py custom list -r ws-applications-{filename}
python cli_ws_image.py custom list -r ws-applications-{filename} -v 4.0.6
```
### 4.2 view a specific config
```bash
python cli_ws_image.py custom view --name ws-applications-408-jupyter-lab-py39-server.json
python cli_ws_image.py custom view --name ws-applications-408-jupyter-lab-py39-server.json --image-name

python cli_ws_image.py custom view --name ws-applications-jupyter-py39-server.json # it actually works for default config too
```

### 4.3 list packages available to be installed using microdnf from rpmfind
```bash
# list only the channels
python cli_ws_image.py pkg list --channel-only

# list packages under selected channels
python cli_ws_image.py pkg list -c isos -c PowerTools
python cli_ws_image.py pkg list -c isos -c PowerTools --x86-only
python cli_ws_image.py pkg list -c isos -c PowerTools --x86-only --export-fn microdnf_pkg.csv -o

# list packages under all channels
python cli_ws_image.py pkg list --x86-only --export-fn microdnf_pkg.csv -o
```

### 4.4 search for a package (microdnf)
```bash
# search using online info
python cli_ws_image.py pkg search --name libgit2
python cli_ws_image.py pkg search --name libgit2 --x86-only

# search using an existing file exported by pkg list or pkg search command
python cli_ws_image.py pkg search --name libgit2 --x86-only --file microdnf_pkg.csv
```