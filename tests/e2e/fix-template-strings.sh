#!/bin/bash

# 批量修复测试文件中的模板字符串

cd /Volumes/Development/项目提示词/0379-world/tests/e2e/tests

for file in $(find . -name "*.spec.ts"); do
  echo "Processing $file..."
  # 使用perl进行替换，更可靠
  perl -i -pe 's/`\$\{BASE_URL\}/BASE_URL + /g' "$file"
  perl -i -pe 's/`/'"'"'/g' "$file"
done

echo "Done!"
