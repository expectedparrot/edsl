import json
import numpy as np
from sklearn.manifold import TSNE
from IPython.display import display_html


def compute_tsne(embeddings, labels):
    embeddings_np = np.array(embeddings)
    tsne = TSNE(n_components=2, random_state=42)
    tsne_results = tsne.fit_transform(embeddings_np)
    data = [
        {
            "x": float(tsne_results[i, 0]),
            "y": float(tsne_results[i, 1]),
            "label": labels[i],
        }
        for i in range(len(labels))
    ]
    return data


def plot_tsne_in_notebook(embeddings, labels):
    # Compute t-SNE
    data = compute_tsne(embeddings, labels)

    # Convert data to JSON
    data_json = json.dumps(data)

    # HTML content with embedded data
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>t-SNE Plot with D3.js</title>
        <script src="https://d3js.org/d3.v6.min.js"></script>
        <style>
            .tooltip {{
                position: absolute;
                text-align: center;
                width: 80px;
                height: 28px;
                padding: 2px;
                font: 12px sans-serif;
                background: lightsteelblue;
                border: 0px;
                border-radius: 8px;
                pointer-events: none;
            }}
        </style>
    </head>
    <body>
        <svg width="600" height="600"></svg>

        <script>
            // Embedded data
            const data = {data_json};

            const svg = d3.select("svg"),
                width = +svg.attr("width"),
                height = +svg.attr("height");

            // Set up scales
            const x = d3.scaleLinear()
                .domain(d3.extent(data, d => d.x))
                .range([0, width]);
            
            const y = d3.scaleLinear()
                .domain(d3.extent(data, d => d.y))
                .range([height, 0]);

            // Create tooltip
            const tooltip = d3.select("body").append("div")
                .attr("class", "tooltip")
                .style("opacity", 0);

            // Create circles for each point
            svg.selectAll("circle")
                .data(data)
                .enter().append("circle")
                .attr("cx", d => x(d.x))
                .attr("cy", d => y(d.y))
                .attr("r", 5)
                .style("fill", "steelblue")
                .on("mouseover", function(event, d) {{
                    tooltip.transition()
                        .duration(200)
                        .style("opacity", .9);
                    tooltip.html(d.label)
                        .style("left", (event.pageX + 5) + "px")
                        .style("top", (event.pageY - 28) + "px");
                }})
                .on("mouseout", function(d) {{
                    tooltip.transition()
                        .duration(500)
                        .style("opacity", 0);
                }});
        </script>
    </body>
    </html>
    """

    # Write HTML content to a temporary file
    html_file = "tsne_plot.html"
    with open(html_file, "w") as file:
        file.write(html_content)

    # Display the HTML content in an iframe within a Jupyter notebook
    display_html(
        f'<iframe src="{html_file}" width="600" height="600"></iframe>', raw=True
    )


# Example usage
if __name__ == "__main__":
    embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6], [0.7, 0.8, 0.9]]
    labels = ["String 1", "String 2", "String 3"]
    plot_tsne_in_notebook(embeddings, labels)
