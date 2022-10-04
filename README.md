# ⛔️ DEPRECATED

This repository is no longer maintained. Please consider using [And Action](https://github.com/and-action/and-action) instead.

## GitHub Action Deployment (ghd)

#### Personal GitHub Access Token

To use `ghd` you need a personal GitHub access token. 
To create this token, go to your profile settings and click on `Developer settings`. There you can find `Personal access tokens`. Create one with `repo` permissions then export your created token to use ghd.
```
export GITHUB_TOKEN=YourTokenHere
```
For later usage you can set this to your local profile settings.

#### Install dependencies

First ensure that you have a working Poetry installation.
```
poetry install
```

To check if `ghd` is working, just run the following command:
```
poetry run ghd
```

You should see the following output:
```
Usage: ghd [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  deploy     Create new deployment
  inspect    Inspect deployment state history
  list       List deployments
  set-state  Set deployment state
```

#### Link ghd to PATH

To use `ghd` from every location on your system, link the shell wrapper to your PATH.

1. Create a new directory to hold symlink: `mkdir $HOME/.bin`
2. Create symlink to `ghd`: `ln -s ~/path/to/ghd/ghd $HOME/.bin/`
3. Add `export PATH="$HOME/.bin:$PATH"` to `.profile`/`.zshrc`/`.bashrc`/`.bash_profile`/etc.

#### Deployment

To start a deployment with `ghd` you have to switch to the repository directory you want to deploy, then execute the deploy command:
```
ghd deploy
```

`ghd` will ask for some inputs:
```
Ref [c5ff55e7e7d6a1f1d33b58bfb4efc00893cb8d08]: 
Environment (dev, test, live): dev
Transient [y/N]: 
Production [y/N]: 
Check constraints [Y/n]: y
moneymeets/demo-repository@c5ff55e7e7d6a1f1d33b58bfb4efc00893cb8d08 (live/v1-2-gc5ff55e) will be deployed to dev
  transient          no
  production         no
  required contexts  all
  description        Github: Here is your commit message from c5ff55e7e7d6a1f1d33b58bfb4efc00893cb8d08
Start deployment? [y/N]: y
```

The output looks like this:
```
Working in moneymeets/demo-repository
Creating deployment
::set-output name=deployment_id::123456789
```

#### Deployment check

You can check the triggered deployment with the inspect command by specifying the deployment id:
```
ghd inspect 123456789
```

Output:
```
Working in moneymeets/demo-repository
state        environment    creator              created               description
-----------  -------------  -------------------  --------------------  -------------
success      dev            github-actions[bot]  2020-02-06T08:32:52Z
in_progress  dev            github-actions[bot]  2020-02-06T08:32:48Z
```

#### Deployment history

If you need only the history of deployments, use:
```
ghd list
```

For detailed information use `-v`, you can limit you history with `-l`. Note that `-v` is disabled by default, as the detailed state (`status_changed` and `state`) requires requests to the GitHub API for every deployment.
```
ghd list -l 7 -v
```

Output:
```
Working in moneymeets/demo-repository

       id  ref      task    environment    creator      created               status_changed        transient    production    state    description
---------  -------  ------  -------------  -----------  --------------------  --------------------  -----------  ------------  -------  ----------------
123456789  0695e4c  deploy  dev            demo-user2   2020-02-06T08:32:10Z  2020-02-06T08:32:52Z  no           no            success  Deployed via GHD
223456789  0695e4c  deploy  dev            demo-user1   2020-02-06T08:24:18Z  2020-02-06T08:25:03Z  no           no            success  Deployed via GHD
323456789  0695e4c  deploy  dev            demo-user1   2020-02-06T08:00:36Z  unknown               no           no            unknown  Deployed via GHD
423456789  40bd8c8  deploy  dev            demo-user2   2020-01-24T09:00:24Z  2020-01-24T09:01:10Z  no           no            success  Deployed via GHD
523456789  40bd8c8  deploy  dev            demo-user1   2020-01-24T08:58:15Z  2020-01-24T08:59:00Z  no           no            success  Deployed via GHD
623456789  8857621  deploy  dev            demo-user2   2020-01-23T08:27:47Z  2020-01-23T08:33:22Z  no           no            success  Deployed via GHD
723456789  74d43f0  deploy  dev            demo-user1   2020-01-23T08:07:28Z  2020-01-23T08:12:51Z  no           no            failure  Deployed via GHD
```

#### Disable environment

You can disable an environment, this will hide the environment from the GitHub UI. Note that this doesn't affect the number of environments shown on the main repository page.
```
ghd set-state -d 12345 -e env inactive
```

#### Integration with [tig](https://github.com/jonas/tig/)

To integrate with [tig](https://github.com/jonas/tig/), you can for example add a binding in `~/.tigrc` to deploy a selected commit by adding `bind main D !ghd deploy --ref %(commit)` to it.
