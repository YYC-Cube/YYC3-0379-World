# scripts/tools — 项目工具脚本

代码规范检查和自动修复工具集。

## 工具清单

| 脚本 | 说明 |
|------|------|
| `check_code_compliance.py` | 检查代码文件的标头注释合规性 |
| `check_directory_structure.py` | 检查项目目录结构是否符合规范 |
| `check_naming_convention.py` | 检查文件命名规范 |
| `check_project_completeness.py` | 检查项目完整性（文档、配置、测试） |
| `fix_code_headers.py` | 自动为代码文件添加规范标头 |
| `fix_documentation.py` | 自动为Markdown文档添加YAML Front Matter |
| `cleanup_project.sh` | 清理临时文件和检查脚本 |

## 使用方式

```bash
python scripts/tools/check_code_compliance.py
python scripts/tools/check_directory_structure.py
python scripts/tools/fix_code_headers.py
```
