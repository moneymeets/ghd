#!/usr/bin/env bash

git_path=$(git rev-parse --show-toplevel)

poetry run pre-commit install -f --hook-type pre-commit
mv "$git_path/.git/hooks/pre-commit" "$git_path/.git/hooks/pre-commit-python"

cat <<EOF > "$git_path/.git/hooks/pre-commit"
#!/usr/bin/env bash
source ${VIRTUAL_ENV}/bin/activate
DIR="\$( cd "\$( dirname "\${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
python \${DIR}/pre-commit-python
EOF

chmod +x "$git_path/.git/hooks/pre-commit"
