# Fork synchronization

`origin` is `youngzyl/Jiangtherapee-Super-Resolution-World-Best`.
`upstream` is `y-g-jiang/Jiangtherapee-Super-Resolution-World-Best`.

The **Sync upstream** GitHub Actions workflow merges upstream `main` into this
fork's `main` every six hours (00:23, 06:23, 12:23, 18:23 UTC; 08:23, 14:23,
20:23, 02:23 Taipei time). It also supports manual runs from the Actions tab.
Scheduled runs may be delayed by GitHub.

The workflow preserves fork commits, including macOS support. It never resets
or force-pushes the branch. Merge conflicts stop the run without pushing;
resolve them locally, then push and run the workflow again. A concurrent push
also causes a safe failure; rerun after fetching the latest branch.

GitHub disables scheduled workflows in public repositories after 60 days
without repository activity. If upstream has been quiet for that long,
re-enable the workflow in Actions. See
[GitHub's workflow documentation](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows?tool=cli).

For a local checkout:

```sh
git remote add upstream https://github.com/y-g-jiang/Jiangtherapee-Super-Resolution-World-Best.git
git fetch upstream main
git merge --no-edit upstream/main
git push origin main
```

Skip `git remote add` if the remote is already configured. The scheduled
workflow updates GitHub; update local files with `git pull --ff-only`.
