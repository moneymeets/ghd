#!/usr/bin/env bash

git_path=$(git rev-parse --show-toplevel)

(cd docker && poetry run pre-commit install -f --hook-type pre-commit)
mv "$git_path/.git/hooks/pre-commit" "$git_path/.git/hooks/pre-commit-python"

cat <<EOF > "$git_path/.git/hooks/pre-commit"
#!/usr/bin/env bash
cd docker && poetry run "$git_path/.git/hooks/pre-commit-python"
EOF

chmod +x "$git_path/.git/hooks/pre-commit"
