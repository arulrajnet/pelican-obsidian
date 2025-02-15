import os
import re
from itertools import chain
from pathlib import Path

from pelican import signals
from pelican.plugins.yaml_metadata.yaml_metadata import YAMLMetadataReader
from pelican.urlwrappers import Tag

ARTICLE_PATHS = {}
FILE_PATHS = {}

link = r'\[\[\s*(?P<filename>[^|\]]+)(\|\s*(?P<linkname>.+))?\]\]'
file_re = re.compile(r'!' + link)
link_re = re.compile(link)


"""
# Test cases
[[my link]]
[[ my work ]]
[[ my work | is finished ]]

![[ a file.jpg ]]
![[file.jpg]]
"""


def get_file_and_linkname(match):
    group = match.groupdict()
    filename = group['filename'].strip()
    linkname = group['linkname'] if group['linkname'] else filename
    linkname = linkname.strip()
    return filename, linkname


class ObsidianMarkdownReader(YAMLMetadataReader):
    """
    Change the format of various links to the accepted case of pelican.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def replace_obsidian_links(self, text):
        """
        Filters all text and replaces matching links with the correct format for pelican. NOTE - this parses all text.
        Args:
            text: Text for entire page
        Return: text with links replaced if possible
        """
        def link_replacement(match):
            filename, linkname = get_file_and_linkname(match)
            path = ARTICLE_PATHS.get(filename)
            if path:
                link_structure = '[{linkname}]({{filename}}{path}{filename}.md)'.format(
                    linkname=linkname, path=path, filename=filename
                )
            else:
                link_structure = '{linkname}'.format(linkname=linkname)
            return link_structure

        def file_replacement(match):
            filename, linkname = get_file_and_linkname(match)
            path = FILE_PATHS.get(filename)
            if path:
                link_structure = '![{linkname}]({{static}}{path}{filename})'.format(
                    linkname=linkname, path=path, filename=filename
                )
            else:
                # don't show it at all since it will be broken
                link_structure = ''

            return link_structure

        text = file_re.sub(file_replacement, text)
        text = link_re.sub(link_replacement, text)
        return text

    def _load_yaml_metadata(self, text, source_path):
        metadata = super()._load_yaml_metadata(text, source_path)
        tags = metadata.get("tags", [])
        mod_tags = []
        for tag in tags:
            if ',' in tag.name:
                str_tags = tag.name.split(",")
                for str_tag in str_tags:
                    url_tag = Tag(str_tag, settings=self.settings)
                    mod_tags.append(url_tag)
            else:
                mod_tags.append(tag)

        metadata["tags"] = mod_tags
        return metadata

    def read(self, source_path):
        """
        Parse content and metadata of markdown files.
        Also changes the links to the acceptable format for pelican
        """

        content, metadata = super().read(source_path)
        content = self.replace_obsidian_links(content)
        return content, metadata


def populate_files_and_articles(article_generator):
    """
    Populates the ARTICLE_PATHS and FILE_PATHS global variables. This is used to find file paths and article paths after
    parsing the wililink articles.
    ARTICLE_PATHS is a dictionary where the key is the filename and the value is the path to the article.
    FILE_PATHS is a dictionary where the key is the file extension and the value is the path to the file

    Args:
        article_generator: built in class.
    Returns: None - sets the ARTICLE_PATHS and FILE_PATHS global variables.
    """
    global ARTICLE_PATHS
    global FILE_PATHS

    base_path = Path(article_generator.path)
    articles = base_path.glob('**/*.md')
    # Get list of all markdown files
    for article in articles:
        full_path, filename_w_ext = os.path.split(article)
        filename, ext = os.path.splitext(filename_w_ext)
        path = str(full_path).replace(str(base_path), '') + '/'

        # This work on both pages and posts/articles
        ARTICLE_PATHS[filename] = path

    # Get list of all other relavant files
    globs = [base_path.glob('**/*.{}'.format(ext)) for ext in ['png', 'jpg', 'svg', 'apkg', 'gif']]
    files = chain(*globs)
    for _file in files:
        full_path, filename_w_ext = os.path.split(_file)
        path = str(full_path).replace(str(base_path), '') + '/'
        FILE_PATHS[filename_w_ext] = path


def modify_generator(generator):
    populate_files_and_articles(generator)
    generator.readers.readers['md'] = ObsidianMarkdownReader(generator.settings)


def modify_metadata(article_generator, metadata):
    """
    Modify the tags so we can define the tags as we are used to in obsidian.
    """
    for tag in metadata.get('tags', []):
        if '#' in tag.name:
            tag.name = tag.name.replace('#', '')


def register():
    signals.article_generator_context.connect(modify_metadata)
    signals.article_generator_init.connect(modify_generator)

    signals.page_generator_context.connect(modify_metadata)
    signals.page_generator_init.connect(modify_generator)
