# Cheat Sheet

## 0. Preparation: specify if not in watson studio
```bash
export BASE_URL=******
export USERNAME=******
export APIKEY=******
```

## 1. Get base image names
### latest cpd version
```bash
python cli_ws_image.py default list --cpu
python cli_ws_image.py default list --service ws --cpu # default service is ws
python cli_ws_image.py default list --service wml --cpu

python cli_ws_image.py default list --gpu
python cli_ws_image.py default list -a
python cli_ws_image.py default list --rstudio

python cli_ws_image.py default list --cpu --export-fn base_images_nongpu_408.txt -o
python cli_ws_image.py default list --cpu --export-fn base_images_nongpu_408.txt

python cli_ws_image.py default list --rstudio --export-fn base_images_rstudio_407.txt
```

### historical cpd version
```bash
python cli_ws_image.py default list -a --cpd-version 4.0.6

python cli_ws_image.py default list --rstudio --cpd-version 4.0.7 --export-fn base_images_rstudio_407.txt
python cli_ws_image.py default list --rstudio --cpd-version 4.0.8 --export-fn base_images_rstudio_408.txt

python cli_ws_image.py default list --service wml --cpu --cpd-version 4.0.7 --export-fn base_images_wmlpython_407.txt
```

## 2. Build and push custom images
```bash
python cli_ws_image.py custom build --registry-url us.icr.io --registry-namespace custom-image-cli-test --dir-dockerfile ../custom-image --base-image-list base_images_nongpu_408.txt --custom-image-name-pattern {image_name}-ws-applications

python cli_ws_image.py custom build --registry-url us.icr.io --registry-namespace cpd-custom-image --dir-dockerfile . --base-image-list base_images_wmlpython_407.txt --custom-image-name-pattern {image_name}-custom
```

## 3. Register custom images in watson studio
```bash
python cli_ws_image.py custom register --jupyter --dry-run
python cli_ws_image.py custom register --jupyterlab --dry-run
python cli_ws_image.py custom register --jupyter-all --dry-run
python cli_ws_image.py custom register --jupyter-all -py 3.8 -v 4.0.6 --dry-run

python cli_ws_image.py custom register --jupyter-all -c ws-applications-408-{filename} -d "{display_name} (ws applications)" -i us.icr.io/custom-image-ws-applications/{image_name}-ws-applications:4.0.8 -v 4.0.8 --dry-run
python cli_ws_image.py custom register --gpu --jupyter-all -c ws-applications-408-{filename} -d "{display_name} (ws applications)" -i us.icr.io/custom-image-ws-applications/{image_name}-ws-applications:4.0.8 -v 4.0.8 --dry-run

python cli_ws_image.py custom register --rstudio -c custom-407-{filename} -d "{display_name} (custom)" -i us.icr.io/custom-image-ws-applications/{image_name}-custom:16 -v 4.0.7 --dry-run
```

## 4. Other commnds
### 4.1 list custom configs
```bash
python cli_ws_image.py custom list -c ws-applications-{filename}
python cli_ws_image.py custom list -c ws-applications-{filename} -v 4.0.6
```
### 4.2 view a specific config
```bash
python cli_ws_image.py custom view --name ws-applications-408-jupyter-lab-py39-server.json
python cli_ws_image.py custom view --name ws-applications-408-jupyter-lab-py39-server.json --image-name

python cli_ws_image.py custom view --name ws-applications-jupyter-py39-server.json # it actually works for default config too
```
