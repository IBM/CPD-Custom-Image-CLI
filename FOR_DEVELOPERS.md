# Notes for Developers

## How to update the doc
Modify the existing Markdown files as needed.

If you want to add a page or re-organize the pages, you will need to change the `index.rst` file.

Once you are done, run the following command to re-build the doc:
```bash
cd docs/
sphinx-build . _build
```

Preview the updated doc by opening the `_build/index.html` in your browser.

## How to view the updated content on GitHub
If you modified something in the doc and pushed to GitHub, it is possible that you don't see any different in GitHub Pages.

In this case, you will need to **clear the cache and open GitHub Pages again**.
