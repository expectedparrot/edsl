import os
from pylint.pyreverse.main import Run

# Example list of projects and their paths
projects = [
    ("jobs", "edsl/jobs"),
    ("interviews", "edsl/jobs/interviews/"),
    ("agents", "edsl/agents"),
    ("data", "edsl/data"),
    ("language_models", "edsl/language_models"),
    ("results", "edsl/results"),
    ("scenarios", "edsl/scenarios"),
    ("surveys", "edsl/surveys"),
    ("utilities", "edsl/utilities"),
    ("coop", "edsl/coop"),
    ("prompts", "edsl/prompts"),
    ("questions", "edsl/questions"),
    ("data_transfer_models", "edsl/data_transfer_models"),
    ("enums", "edsl/enums"),
    ("config", "edsl/config"),
    ("Base", "edsl/Base"),
]

output_dir = ".temp/visualize_structure"
index_file_path = os.path.join(output_dir, "index.html")


def generate_diagrams(projects):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    with open(index_file_path, "w") as index_file:
        index_file.write("<html><body>\n")

        for name, path in projects:
            print("Generating diagrams for", name, "from", path)
            # Constructing command line arguments
            args = ["-o", "svg", "-d", output_dir, "-p", name, path]

            # Generating diagrams
            try:
                Run(args)
            except SystemExit:
                pass

            # Add entry to index.html for each diagram
            index_file.write(f"<h1>{name} ({path})</h1>\n")
            for diagram_type in ["classes", "packages"]:
                index_file.write(f"<h2>{diagram_type}</h2>\n")
                image_path = f"{diagram_type}_{name}.svg"
                index_file.write(
                    f"<img src='{image_path}' alt='{name} {diagram_type} diagram'>\n"
                )

        index_file.write("</body></html>")


generate_diagrams(projects)
