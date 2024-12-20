from collections import defaultdict
from typing import List, Dict, Any
import json


class FoldableHTMLTableGenerator:
    def __init__(self, data: List[Dict[str, Any]]):
        self.data = data

    def tree(self, fold_attributes: List[str], drop: List[str] = None) -> Dict:
        def nested_dict():
            return defaultdict(nested_dict)

        result = nested_dict()
        drop = drop or []  # Use an empty list if drop is None

        for item in self.data:
            current = result
            for attr in fold_attributes:
                current = current[item[attr]]

            row = {
                k: v
                for k, v in item.items()
                if k not in fold_attributes and k not in drop
            }
            if "_rows" not in current:
                current["_rows"] = []
            current["_rows"].append(row)

        return result

    def generate_html(self, tree, fold_attributes: List[str]) -> str:
        html_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Foldable Nested Table</title>
            <style>
                .folding-section { margin-left: 20px; }
                .fold-button { cursor: pointer; margin: 5px 0; }
                table { border-collapse: collapse; margin-top: 10px; }
                th, td { border: 1px solid black; padding: 5px; }
                .attribute-label { font-weight: bold; }
            </style>
        </head>
        <body>
            <div id="root"></div>
            <script>
            function toggleFold(id) {
                const element = document.getElementById(id);
                element.style.display = element.style.display === 'none' ? 'block' : 'none';
            }

            function createFoldableSection(data, path = [], attributes = %s) {
                const container = document.createElement('div');
                container.className = 'folding-section';

                for (const [key, value] of Object.entries(data)) {
                    if (key === '_rows') {
                        const table = document.createElement('table');
                        const headerRow = table.insertRow();
                        const headers = Object.keys(value[0]);
                        headers.forEach(header => {
                            const th = document.createElement('th');
                            th.textContent = header;
                            headerRow.appendChild(th);
                        });
                        value.forEach(row => {
                            const tableRow = table.insertRow();
                            headers.forEach(header => {
                                const cell = tableRow.insertCell();
                                cell.textContent = row[header];
                            });
                        });
                        container.appendChild(table);
                    } else {
                        const button = document.createElement('button');
                        const attributeType = attributes[path.length];
                        button.innerHTML = `<span class="attribute-label">${attributeType}:</span> ${key}`;
                        button.className = 'fold-button';
                        const sectionId = `section-${path.join('-')}-${key}`;
                        button.onclick = () => toggleFold(sectionId);
                        container.appendChild(button);

                        const section = document.createElement('div');
                        section.id = sectionId;
                        section.style.display = 'none';
                        section.appendChild(createFoldableSection(value, [...path, key], attributes));
                        container.appendChild(section);
                    }
                }

                return container;
            }

            const treeData = %s;
            document.getElementById('root').appendChild(createFoldableSection(treeData));
            </script>
        </body>
        </html>
        """

        return html_content % (json.dumps(fold_attributes), json.dumps(tree))

    def save_html(self, fold_attributes: List[str], filename: str = "output.html"):
        tree = self.tree(fold_attributes)
        html_content = self.generate_html(tree, fold_attributes)

        with open(filename, "w", encoding="utf-8") as f:
            f.write(html_content)

        print(f"HTML file has been generated: {filename}")
