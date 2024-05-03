import os
import markdown
import pdfkit
import tempfile
import yaml
import re
import html
from git import Repo, RemoteProgress
from datetime import datetime
from packaging import version
from tqdm import tqdm


def process_image_paths(md_content):
    # Define a regular expression pattern to find image tags
    pattern = r'src(?:Light|Dark)="(.*?)"'

    # Function to replace the relative path with an absolute path
    def replace(match):
        relative_path = match.group(1)
        absolute_path = f'{base_path}{relative_path}{path_args}'

        # Print the original and new image URLs for debugging
        return f'src="{absolute_path}"'

    # Use the sub method to replace all occurrences
    return re.sub(pattern, replace, md_content)


def preprocess_code_blocks(md_content):
    # Regular expression to match extended code blocks with filename and language
    pattern = r'```(\w+)?\s+filename="([^"]+)"\s*(switcher)?\n(.*?)```'

    def replace(match):
        language = match.group(1) if match.group(1) else ''
        filename = match.group(2)
        code_block = match.group(4)

        # Format the header with filename and language
        header = f'<div class="code-header"><i>{filename} ({language})</i></div>' if language else f'<div class="code-header"><i>{filename}</i></div>'

        return f'{header}\n```{language}\n{code_block}\n```'

    # Replace all occurrences in the content
    return re.sub(pattern, replace, md_content, flags=re.DOTALL)


def safe_load_frontmatter(frontmatter_content):
    try:
        return yaml.safe_load(frontmatter_content)
    except yaml.YAMLError:
        return None


def preprocess_mdx_content(md_content):
    # Replace HTML tags in frontmatter
    md_content = re.sub(r'<(/?\w+)>', lambda m: html.escape(m.group(0)), md_content)
    return md_content


def parse_frontmatter(md_content):
    lines = md_content.split('\n')
    if lines[0].strip() == '---':
        end_of_frontmatter = lines.index('---', 1)
        frontmatter = '\n'.join(lines[1:end_of_frontmatter])
        content = '\n'.join(lines[end_of_frontmatter + 1:])
        return frontmatter, content
    return None, md_content


class CloneProgress(RemoteProgress):
    def __init__(self):
        super().__init__()
        self.pbar = tqdm()

    def update(self, op_code, cur_count, max_count=None, message=''):
        if max_count is not None:
            self.pbar.total = max_count
        self.pbar.update(cur_count - self.pbar.n)  # increment the pbar with the increment

    def finalize(self):
        self.pbar.close()

# Clone a specific directory of a repository / branch
def clone_repo(repo_url, branch, docs_dir, repo_dir):
    # Initialize and configure the repository for sparse checkout
    if not os.path.isdir(repo_dir):
        os.makedirs(repo_dir, exist_ok=True)
        print("Cloning repository...")
        repo = Repo.init(repo_dir)
        with repo.config_writer() as git_config:
            git_config.set_value("core", "sparseCheckout", "true")

        # Define the sparse checkout settings
        with open(os.path.join(repo_dir, ".git/info/sparse-checkout"), "w") as sparse_checkout_file:
            sparse_checkout_file.write(f"/{docs_dir}\n")

        # Pull the specific directory from the repository
        origin = repo.create_remote("origin", repo_url)
        origin.fetch(progress=CloneProgress())
        repo.git.checkout(branch)
        print("Repository cloned.")

    # Update the repository if it already exists
    else:
        print("Repository already exists. Updating...")
        repo = Repo(repo_dir)
        origin = repo.remotes.origin
        origin.fetch(progress=CloneProgress())
        repo.git.checkout(branch)
        origin.pull(progress=CloneProgress())
        print("Repository updated.")


def is_file_open(file_path):
    if not os.path.exists(file_path):
        return False  # File does not exist, so it's not open

    try:
        # Try to open the file in append mode. If the file is open in another program, this might fail
        with open(file_path, 'a'):
            pass
        return False
    except PermissionError:
        # If a PermissionError is raised, it's likely the file is open elsewhere
        return True


def get_files_sorted(root_dir):
    all_files = []

    # Step 1: Traverse the directory structure
    for root, _, files in os.walk(root_dir):
        for file in files:
            full_path = os.path.join(root, file)

            # Step 2: Prioritize 'index.mdx' or 'index.md' within the same folder
            modified_basename = '!!!' + file if file in ['index.mdx', 'index.md'] else file
            sort_key = os.path.join(root, modified_basename)

            # Add tuple to the list
            all_files.append((full_path, sort_key))

    # Step 3: Perform a global sort based on modified basename
    all_files.sort(key=lambda x: x[1])

    # Step 4: Return the full paths in sorted order
    return [full_path for full_path, _ in all_files]


def preprocess_frontmatter(frontmatter):
    # Dictionary to store HTML tags and their placeholders
    html_tags = {}

    # Function to replace HTML tags with placeholders
    def replace_tag(match):
        tag = match.group(0)
        placeholder = f"HTML_TAG_{len(html_tags)}"
        html_tags[placeholder] = tag
        return placeholder

    # Replace HTML tags with placeholders
    modified_frontmatter = re.sub(r'<[^>]+>', replace_tag, frontmatter)

    return modified_frontmatter, html_tags


def restore_html_tags(parsed_data, html_tags):
    if isinstance(parsed_data, dict):
        for key, value in parsed_data.items():
            if isinstance(value, str):
                for placeholder, tag in html_tags.items():
                    value = value.replace(placeholder, tag)
                # if key == 'title':  # Escape HTML characters for titles
                value = html.escape(value)
                parsed_data[key] = value
    return parsed_data


def process_files(files, repo_dir, docs_dir):
    # Initialize the Table of Contents
    toc = ""  
    html_all_pages_content = ""

    # Initialize an empty string to hold all the HTML content & Include the main CSS directly in the HTML
    html_header = f"""
    <html>
    <head>
        <style>
            {open('styles.css').read()}
        </style>
    </head>
    <body>
    """

    numbering = [0]  # Starting with the first level

    for index, file_path in enumerate(files):
        with open(file_path, 'r', encoding='utf8') as f:
            md_content = f.read()

            # Process the markdown content for image paths
            if Change_img_url:
                md_content = process_image_paths(md_content)

            # Process the markdown content for non standard code blocks
            md_content = preprocess_code_blocks(md_content)

            # Parse the frontmatter and markdown
            frontmatter, md_content = parse_frontmatter(md_content)

            if frontmatter:
                # Preprocessing: replaces HTML tags with unique placeholders and stores the mappings
                frontmatter, html_tags = preprocess_frontmatter(frontmatter)

                # Parse the YAML frontmatter
                data = safe_load_frontmatter(frontmatter)
                if data is not None:

                    # Preprocessing: After parsing the YAML, restore the HTML tags in place of the placeholders
                    data = restore_html_tags(data, html_tags)
                
                    # Depth Level: Calculate relative path, directory depth and TOC
                    rel_path = os.path.relpath(file_path, os.path.join(repo_dir, docs_dir))

                    # Depth Level: Calculate the depth of each section
                    depth = rel_path.count(os.sep)  # Count separators to determine depth
                    file_basename = os.path.basename(file_path)                    
                    if file_basename.startswith("index.") and depth > 0:
                        depth += -1  # or another title for the main index
                    indent = '&nbsp;' * 5 * depth  # Adjust indentation based on depth

                    # Numbering: Ensure numbering has enough levels
                    while len(numbering) <= depth:
                        numbering.append(0)

                    # Numbering: Increment at the current level
                    numbering[depth] += 1

                    # Numbering: Reset for any lower levels
                    for i in range(depth + 1, len(numbering)):
                        numbering[i] = 0
                    
                    # Numbering: Create entry
                    toc_numbering = f"{'.'.join(map(str, numbering[:depth + 1]))}"

                    # TOC: Generate the section title
                    toc_title = data.get('title', os.path.splitext(os.path.basename(file_path))[0].title())
                    toc_full_title = f"{toc_numbering} - {toc_title}"
                    toc += f"{indent}<a href='#{toc_full_title}'>{toc_full_title}</a><br/>"

                    # Page Content: Format the parsed YAML to HTML
                    html_page_content = f"""
                    <h1>{toc_full_title}</h1>
                    <div class="doc-path"><p>Documentation path: {file_path.replace(chr(92),'/').replace('.mdx', '').replace(repo_dir + '/' + docs_dir,'')}</p></div>
                    <p><strong>Description:</strong> {data.get('description', 'No description')}</p>
                    """
                    if data.get('related', {}):
                        html_page_content += f"""
                        <div style="margin-left:20px;">
                            <p><strong>Related:</strong></p>
                            <p><strong>Title:</strong> {data.get('related', {}).get('title', 'Related')}</p>
                            <p><strong>Related Description:</strong> {data.get('related', {}).get('description', 'No related description')}</p>
                            <p><strong>Links:</strong></p>
                        <ul>
                            {''.join([f'<li>{link}</li>' for link in data.get('related', {}).get('links', [])])}
                        </ul>
                        </div>
                        """
                    html_page_content += '</br>'

                else:
                    html_page_content = ""
            else:
                html_page_content = ""

            # Convert Markdown to HTML with table support and add content to the identified header
            html_page_content += markdown.markdown(md_content, extensions=['fenced_code', 'codehilite', 'tables', 'footnotes', 'toc', 'abbr', 'attr_list', 'def_list', 'smarty', 'admonition'])
            
            # Add page content to all cumulated pages content
            html_all_pages_content += html_page_content

            # Add a page break unless it is the last file
            if index < len(files) - 1:
                html_all_pages_content += '<div class="page-break"></div>'
    
    # Prepend the ToC to the beginning of the HTML content
    toc_html = f"""<div style="padding-bottom: 10px"><div style="padding-bottom: 20px"><h1>Table of Contents</h1></div>{toc}</div><div style="page-break-before: always;">"""
    html_all_content = toc_html + html_all_pages_content

    # Finalize html formatting
    html_all_pages_content  = html_header + html_all_pages_content + "</body></html>"
    toc_html                = html_header + toc_html + "</body></html>"
    html_all_content        = html_header + html_all_content + "</body></html>"

    return(html_all_content, toc_html, html_all_pages_content)


def find_latest_version(html_content):
    # Regular expression to find versions like v14.2.0
    version_pattern = re.compile(r"v(\d+\.\d+\.\d+)")
    versions = version_pattern.findall(html_content)
    # Remove duplicates and sort versions
    unique_versions = sorted(set(versions), key=lambda v: version.parse(v), reverse=True)
    return unique_versions[0] if unique_versions else None


if __name__ == "__main__":

    # Define the output PDF file name
    # project_title = "Next.js v14 Documentation"
    # output_pdf = "Next.js_v14_Documentation.pdf"
    export_html = False

    # Clone the repository and checkout the canary branch
    repo_dir = "nextjs-docs" 
    repo_url = "https://github.com/vercel/next.js.git"
    branch = "canary"
    docs_dir = "docs"

    # Define a base path and quality for the image URLs
    Change_img_url = True
    base_path = "https://nextjs.org/_next/image?url="
    path_args = "&w=1920&q=75"

    # Clone the repository
    clone_repo(repo_url, branch, docs_dir, repo_dir)

    # Traverse the docs directory and convert each markdown file to HTML
    print ("Converting the Documentation to HTML...")
    docs_dir_full_path = os.path.join(repo_dir, docs_dir)
    files_to_process = get_files_sorted(docs_dir_full_path)
    html_all_content, _, _ = process_files(files_to_process, repo_dir, docs_dir)
    print("Converted all MDX to HTML.")

    # Save the HTML content to a file for inspection
    if export_html:
        with open('output.html', 'w', encoding='utf8') as f:
            f.write(html_all_content)
            print("HTML Content exported.")

    # Find the latest version in the HTML content
    latest_version = find_latest_version(html_all_content)
    if latest_version:
        project_title = f"Next.js v{latest_version} Documentation"
        output_pdf = f"Next.js_v{latest_version}_Documentation.pdf"
    else:
        project_title = "Next.js Documentation"
        output_pdf = "Next.js_Documentation.pdf"

    # Define the cover HTML with local CSS file
    cover_html = f"""
    <html>
        <head>
            <style>
                {open('styles.css').read()}
            </style>
        </head>
        <body>
            <div class="master-container">
                <div class="container">
                    <div class="title">{project_title}</div>
                    <div class="date">Date: {datetime.now().strftime("%Y-%m-%d")}</div>
                </div>
            </div>
        </body>
    </html>
    """

    # Write the cover HTML to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.html') as cover_file:
        cover_file.write(cover_html.encode('utf-8'))
        print("HTML Cover exported.")

    # Convert the combined HTML content to PDF with a cover and a table of contents
    if is_file_open(output_pdf):
        print("The output file is already open in another process. Please close it and try again.")
    else:
        options = {
            'encoding': 'UTF-8',
            'page-size': 'A4',
            'quiet': '',
            'image-dpi': 150, # General reco.: printer - hq, 300 dpi| ebook - low quality, 150 dpi| screen-view-only quality, 72 dpi
            'image-quality': 75,
            # 'no-outline': None,
            # 'no-images': None,
        }
        pdfkit.from_string(html_all_content, output_pdf, options=options, cover=cover_file.name, toc={})
        print("Created the PDF file successfully.")

    # Delete the temporary file
    os.unlink(cover_file.name)