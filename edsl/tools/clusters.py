import json
import numpy as np
from sklearn.cluster import KMeans
from sklearn.manifold import TSNE
from sklearn.decomposition import PCA
from IPython.display import display_html


def compute_tsne(embeddings, cluster_labels, text_labels):
    """
    Compute t-SNE on embedding vectors.

    Parameters:
    embeddings (np.ndarray): The embedding vectors.
    cluster_labels (np.ndarray): Cluster labels for each embedding.
    text_labels (list): Text labels for each embedding.

    Returns:
    list: List of dictionaries with x, y coordinates, cluster labels, and text labels.
    """
    tsne = TSNE(n_components=2, random_state=42)
    tsne_results = tsne.fit_transform(embeddings)
    data = [
        {
            "x": float(tsne_results[i, 0]),
            "y": float(tsne_results[i, 1]),
            "cluster_label": str(cluster_labels[i]),
            "text_label": text_labels[i],
        }
        for i in range(len(cluster_labels))
    ]
    return data


def compute_pca(embeddings, cluster_labels, text_labels):
    """
    Compute PCA on embedding vectors.

    Parameters:
    embeddings (np.ndarray): The embedding vectors.
    cluster_labels (np.ndarray): Cluster labels for each embedding.
    text_labels (list): Text labels for each embedding.

    Returns:
    list: List of dictionaries with x, y coordinates, cluster labels, and text labels.
    """
    pca = PCA(n_components=2)
    pca_results = pca.fit_transform(embeddings)
    data = [
        {
            "x": float(pca_results[i, 0]),
            "y": float(pca_results[i, 1]),
            "cluster_label": str(cluster_labels[i]),
            "text_label": text_labels[i],
        }
        for i in range(len(cluster_labels))
    ]
    return data


def plot(embeddings, text_labels, n_clusters=5, method="tsne"):
    """
    Perform k-means clustering and plot results in a Jupyter notebook using D3.js.

    Parameters:
    embeddings (np.ndarray): The embedding vectors.
    text_labels (list): Text labels for each embedding.
    n_clusters (int): The number of clusters to form.
    method (str): The dimensionality reduction method to use ('tsne' or 'pca').
    """
    # Perform k-means clustering
    kmeans = KMeans(n_clusters=n_clusters, random_state=42)
    cluster_labels = kmeans.fit_predict(embeddings)

    # Compute dimensionality reduction
    if method == "tsne":
        data = compute_tsne(embeddings, cluster_labels, text_labels)
    elif method == "pca":
        data = compute_pca(embeddings, cluster_labels, text_labels)
    else:
        raise ValueError("Invalid method. Choose 'tsne' or 'pca'.")

    # Convert data to JSON
    data_json = json.dumps(data)

    # HTML content with embedded data
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>t-SNE/PCA Plot with D3.js</title>
        <script src="https://d3js.org/d3.v6.min.js"></script>
        <style>
            .tooltip {{
                position: absolute;
                text-align: center;
                width: auto;
                height: auto;
                padding: 2px;
                font: 12px sans-serif;
                background: lightsteelblue;
                border: 0px;
                border-radius: 8px;
                pointer-events: none;
            }}
            .dot {{
                stroke: #000;
                stroke-width: 0.5;
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

            // Set up color scale
            const color = d3.scaleOrdinal(d3.schemeCategory10);

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
                .attr("class", "dot")
                .style("fill", d => color(d.cluster_label))
                .on("mouseover", function(event, d) {{
                    tooltip.transition()
                        .duration(200)
                        .style("opacity", .9);
                    tooltip.html(d.text_label)
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
    html_file = "tsne_pca_plot.html"
    with open(html_file, "w") as file:
        file.write(html_content)

    # Display the HTML content in an iframe within a Jupyter notebook
    display_html(
        f'<iframe src="{html_file}" width="600" height="600"></iframe>', raw=True
    )


# Example usage
if __name__ == "__main__":
    # Generate some sample data (embedding vectors)
    np.random.seed(42)
    embedding_vectors = np.random.rand(
        100, 50
    )  # 100 samples with 50-dimensional embeddings
    text_labels = [f"Text {i}" for i in range(100)]  # Sample text labels

    # Plot the clusters using t-SNE
    plot(embedding_vectors, text_labels, n_clusters=5, method="tsne")

    # Plot the clusters using PCA
    plot(embedding_vectors, text_labels, n_clusters=5, method="pca")
