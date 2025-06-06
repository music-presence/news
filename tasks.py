import dateutil.parser
from invoke import task
from invoke.context import Context

from dataclasses import dataclass
from typing import List, Dict, Any, Iterator, Tuple, Optional, Callable
import dataclasses
import datetime
import dateutil
import functools
import json
import pathlib
import os
import sys
import shutil
import copy
import re
import urllib.parse

import jsonschema
import jsonschema.validators
import referencing


NewsId = int
LanguageCode = str
JsonDict = Dict[str, Any]

PWD = os.path.dirname(__file__)
STATIC_DIR = "static"
STATIC_LOCATION = os.path.abspath(os.path.join(PWD, STATIC_DIR))
DIST_DIR = "dist"
DIST_LOCATION = os.path.abspath(os.path.join(PWD, DIST_DIR))
DIST_STATIC_DIR = "static"
DIST_STATIC_ASSETS_DIR = "news-assets"
NEWS_DIR = "news"
NEWS_LOCATION = os.path.abspath(os.path.join(PWD, NEWS_DIR))
META_FILENAME = "meta.json"
DEFAULT_LANGUAGE_CODE = "en"  # English
TRANSLATIONS_DIR = "translations"
TRANSLATIONS_DEFAULT_JSON_FILENAME = f"{DEFAULT_LANGUAGE_CODE}.json"
CONTENT_FILENAME = "content.md"
BANNER_DIR = "banner"
BANNER_FILENAME = "image.png"
BANNER_STRINGS_FILENAME = "strings.txt"
URL_PROTOCOL = "https"
URL_DOMAIN = "news.musicpresence.app"


def read_schema_validator(
    schema_location: str,
) -> Tuple[JsonDict, jsonschema.Validator]:
    try:
        with open(schema_location) as f:
            schema = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(
            f"Error: Could not load schema from {schema_location}: {e}", file=sys.stderr
        )
        sys.exit(1)
    try:
        validator = jsonschema.validators.validator_for(schema)
        validator.check_schema(schema)
    except Exception as e:
        print(f"Error: Invalid schema {schema_location}: {e}", file=sys.stderr)
        sys.exit(1)
    return (schema, validator)


LANGUAGES_SCHEMA_FILENAME = "languages.schema.json"
META_SCHEMA_FILENAME = "meta.schema.json"
NEWS_SCHEMA_FILENAME = "news.schema.json"
SCHEMA_DIR = "schemas"
LANGUAGES_SCHEMA_PATH = f"{SCHEMA_DIR}/{LANGUAGES_SCHEMA_FILENAME}"
META_SCHEMA_PATH = f"{SCHEMA_DIR}/{META_SCHEMA_FILENAME}"
NEWS_SCHEMA_PATH = f"{SCHEMA_DIR}/{NEWS_SCHEMA_FILENAME}"
LANGUAGES_SCHEMA_LOCATION = os.path.abspath(os.path.join(PWD, LANGUAGES_SCHEMA_PATH))
META_SCHEMA_LOCATION = os.path.abspath(os.path.join(PWD, META_SCHEMA_PATH))
NEWS_SCHEMA_LOCATION = os.path.abspath(os.path.join(PWD, NEWS_SCHEMA_PATH))
LANGUAGES_SCHEMA, LanguagesValidator = read_schema_validator(LANGUAGES_SCHEMA_LOCATION)
META_SCHEMA, MetaValidator = read_schema_validator(META_SCHEMA_LOCATION)
NEWS_SCHEMA, NewsValidator = read_schema_validator(NEWS_SCHEMA_LOCATION)
registry = (
    referencing.Registry()
    .with_resource(
        META_SCHEMA_FILENAME,
        referencing.Resource.from_contents(META_SCHEMA),
    )
    .with_resource(
        LANGUAGES_SCHEMA_FILENAME,
        referencing.Resource.from_contents(LANGUAGES_SCHEMA),
    )
    .with_resource(
        NEWS_SCHEMA_FILENAME,
        referencing.Resource.from_contents(NEWS_SCHEMA),
    )
)
LANGUAGES_VALIDATOR: jsonschema.Validator = LanguagesValidator(
    schema=LANGUAGES_SCHEMA, registry=registry
)
META_VALIDATOR: jsonschema.Validator = MetaValidator(
    schema=META_SCHEMA, registry=registry
)
NEWS_VALIDATOR: jsonschema.Validator = NewsValidator(
    schema=NEWS_SCHEMA, registry=registry
)


def translation_out_of_sync(id: NewsId, name: str, current: str, translation: str):
    print(
        f"Error: News {id}: Translation for {name} is out of sync: "
        f'"{translation}" for "{current}"',
        file=sys.stderr,
    )
    sys.exit(1)


def original_translation(translations: Dict[LanguageCode, str]):
    if not DEFAULT_LANGUAGE_CODE in translations:
        print(
            f"Error: Missing default translation in {repr(translations)}",
            file=sys.stderr,
        )
        sys.exit(1)
    return translations[DEFAULT_LANGUAGE_CODE]


def check_translation(
    id: NewsId, name: str, original: str, translations: Dict[LanguageCode, str]
):
    if original_translation(translations) != original:
        translation_out_of_sync(id, name, original, original_translation(translations))


@dataclass
class Filters:
    languages: Optional[List[str]]
    operating_systems: Optional[List[str]]


@dataclass
class Meta:
    published: bool
    start_time: Optional[datetime.datetime]
    end_time: Optional[datetime.datetime]
    filters: Optional[Filters]


@dataclass
class ContentButton:
    aside: bool
    label: str
    url: str


@dataclass
class Content:
    title: str
    banner_path: str
    banner_strings: str
    content: str
    buttons: List[ContentButton]


@dataclass
class Translation:
    title: str
    banner: str
    content: str
    buttons: List[str]

    @classmethod
    def from_content(cls, content: Content):
        return Translation(
            title=content.title,
            banner=content.banner_strings,
            content=content.content,
            buttons=[button.label for button in content.buttons],
        )


@dataclass
class NewsButton:
    label: Dict[LanguageCode, str]
    url: str
    aside: bool

    @classmethod
    def from_content_button_and_translations(
        cls,
        content_button: ContentButton,
        translations: List[Tuple[LanguageCode, str]],
    ):
        return NewsButton(
            label=dict(translations),
            url=content_button.url,
            aside=content_button.aside,
        )


@dataclass
class News:
    id: NewsId
    meta: Meta
    title: Dict[LanguageCode, str]
    banner: Dict[LanguageCode, str]
    content: Dict[LanguageCode, str]
    buttons: List[NewsButton]

    @classmethod
    def create(
        cls,
        id: NewsId,
        meta: Meta,
        content: Content,
        directory: str,
        languages: List[str],
    ):
        result = News(
            id=id,
            meta=meta,
            banner=dict(list(enumerate_translated_banners(directory, languages))),
            title=dict(list(enumerate_translated_titles(directory, languages))),
            content=dict(list(enumerate_translated_contents(directory, languages))),
            buttons=list(
                enumerate_translated_news_buttons(content, directory, languages)
            ),
        )
        banner_strings = dict(
            list(enumerate_translations(directory, languages, "banner"))
        )
        check_translation(id, "title", content.title, result.title)
        check_translation(id, "content", content.content, result.content)
        check_translation(id, "banner", content.banner_strings, banner_strings)
        if len(result.buttons) != len(content.buttons):
            print(
                f"Error: Button count mismatch: "
                f"Expected {len(content.buttons)}, got {len(result.buttons)}",
                file=sys.stderr,
            )
            sys.exit(1)
        for content_button, result_button in zip(content.buttons, result.buttons):
            check_translation(id, "button", content_button.label, result_button.label)
        return result


def to_camel_case(snake_str):
    components = snake_str.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def transform_keys_to_camel_case(obj):
    if isinstance(obj, dict):
        return {
            to_camel_case(k): transform_keys_to_camel_case(v) for k, v in obj.items()
        }
    elif isinstance(obj, list):
        return [transform_keys_to_camel_case(item) for item in obj]
    else:
        return obj


def remove_none_values(obj):
    if isinstance(obj, dict):
        return {k: remove_none_values(v) for k, v in obj.items() if v is not None}
    return obj


@functools.singledispatch
def encode_value(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return transform_keys_to_camel_case(
            remove_none_values(dataclasses.asdict(value))
        )
    return value


@encode_value.register(datetime.datetime)
@encode_value.register(datetime.date)
def _(value: datetime.date | datetime.datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def dict_to_meta(data: JsonDict) -> Meta:
    filters = None
    if "filters" in data:
        filters = Filters(
            languages=data["filters"].get("languages", None),
            operating_systems=data["filters"].get("operatingSystems", None),
        )
    start_time = None
    end_time = None
    if "startTime" in data:
        try:
            start_time = dateutil.parser.parse(data["startTime"])
        except Exception as e:
            print(f"Error: Failed to parse start time: {e}", file=sys.stderr)
    if "endTime" in data:
        try:
            end_time = dateutil.parser.parse(data["endTime"])
        except Exception as e:
            print(f"Error: Failed to parse end time: {e}", file=sys.stderr)
    return Meta(
        start_time=start_time,
        end_time=end_time,
        filters=filters,
        published=data["published"],
    )


def read_file_contents(path: str) -> str:
    if not os.path.exists(path):
        print(f"Error: {path} does not exist", file=sys.stderr)
        sys.exit(1)
    try:
        with open(path, "rt") as file:
            return file.read()
    except Exception as e:
        print(f"Error: Failed to read file {path}: {e}", file=sys.stderr)
        sys.exit(1)


def get_validator_languages(validator: jsonschema.Validator) -> List[str]:
    try:
        return validator.schema["enum"]
    except Exception as e:
        print(
            f"Error: Failed to read languages from meta schema: {e}",
            file=sys.stderr,
        )
        sys.exit(1)


def get_all_languages() -> List[str]:
    return get_validator_languages(LANGUAGES_VALIDATOR)


def get_languages(meta: Meta) -> List[str]:
    if meta.filters is not None and meta.filters.languages is not None:
        return meta.filters.languages
    return get_all_languages()


def enumerate_news_directories() -> Iterator[Tuple[NewsId, str]]:
    for dir_name in os.listdir(NEWS_LOCATION):
        full_path = os.path.join(NEWS_LOCATION, dir_name)
        if not os.path.isdir(full_path):
            print(f"Skipping non-directory {full_path}", file=sys.stderr)
            continue
        if not dir_name.isdigit():
            print(f"Skipping non-numeric directory {dir_name}", file=sys.stderr)
            continue
        yield int(dir_name), full_path


def read_news_meta(
    directory: str, validator: jsonschema.Validator, expected_schema_location: str
) -> Meta:
    meta_path = os.path.abspath(os.path.join(directory, META_FILENAME))
    if not os.path.exists(meta_path):
        print(f"Error: {META_FILENAME} not found in {directory}", file=sys.stderr)
        sys.exit(1)
    try:
        with open(meta_path) as f:
            meta = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {meta_path}: {e}", file=sys.stderr)
        sys.exit(1)
    if "$schema" not in meta:
        print(f"Error: No $schema key in {meta_path}", file=sys.stderr)
        sys.exit(1)
    meta_schema_location = os.path.abspath(os.path.join(directory, meta["$schema"]))
    if meta_schema_location != os.path.abspath(expected_schema_location):
        print(
            f"Error: {META_FILENAME} schema is not the expected schema "
            f"{expected_schema_location}: {meta_schema_location}",
            file=sys.stderr,
        )
        sys.exit(1)
    del meta["$schema"]
    try:
        validator.validate(meta)
    except jsonschema.exceptions.ValidationError as e:
        print(f"Error: {meta_path} failed validation: {e}", file=sys.stderr)
        sys.exit(1)
    return dict_to_meta(meta)


def enumerate_news_items(
    directory: str,
    item_filename: str,
    languages: List[str],
    converter: Callable[[str], str] = lambda e: e,
) -> Iterator[Tuple[LanguageCode, str]]:
    default_item_path = os.path.join(directory, DEFAULT_LANGUAGE_CODE, item_filename)
    if not os.path.exists(default_item_path):
        print(
            f"Error: Expected file does not exist: {default_item_path}",
            file=sys.stderr,
        )
    yield (DEFAULT_LANGUAGE_CODE, converter(default_item_path))
    for dir_name in os.listdir(directory):
        full_path = os.path.join(directory, dir_name)
        if not os.path.isdir(full_path):
            continue
        language = dir_name
        if not language in languages:
            print(
                f"Error: Unexpected language in {directory}: {language}",
                file=sys.stderr,
            )
            sys.exit(1)
        language_item_path = os.path.join(full_path, item_filename)
        yield (language, converter(language_item_path))


def enumerate_translated_banners(
    directory: str, languages: List[str]
) -> Iterator[Tuple[LanguageCode, str]]:
    yield from enumerate_news_items(
        directory=os.path.join(directory, BANNER_DIR),
        item_filename=BANNER_FILENAME,
        languages=languages,
    )


def enumerate_translations(
    directory: str, languages: List[str], key: str
) -> Iterator[Tuple[LanguageCode, Any]]:
    translations_dir = os.path.join(directory, TRANSLATIONS_DIR)
    for language in languages:
        filepath = os.path.join(translations_dir, f"{language}.json")
        if not os.path.exists(filepath):
            print(f"Skipping {filepath}: Language does not exist", file=sys.stderr)
            continue
        try:
            with open(filepath, "rt") as f:
                data = json.loads(f.read())
        except Exception as e:
            print(
                f"Error: Failed to load translation {filepath}: {e}",
                file=sys.stderr,
            )
            sys.exit(1)
        if not key in data or len(str(data[key])) == 0:
            continue
        yield (language, data[key])


def enumerate_translated_titles(
    directory: str, languages: List[str]
) -> Iterator[Tuple[LanguageCode, str]]:
    yield from enumerate_translations(directory, languages, key="title")


def enumerate_translated_contents(
    directory: str, languages: List[str]
) -> Iterator[Tuple[LanguageCode, str]]:
    yield from enumerate_translations(directory, languages, key="content")


def enumerate_translated_button_labels(
    directory: str, languages: List[str]
) -> Iterator[Tuple[LanguageCode, List[str]]]:
    yield from enumerate_translations(directory, languages, key="buttons")


def enumerate_translated_news_buttons(
    content: Content, directory: str, languages: List[str]
) -> Iterator[NewsButton]:
    translated_labels = list(enumerate_translated_button_labels(directory, languages))
    for language, labels in translated_labels:
        # More labels are an error (there should not be more translations),
        # but less is possible when no label after it is translated
        # (that is how Weblate handles it).
        if len(labels) > len(content.buttons):
            print(
                f"Error: Mismatch in content button count and translation count "
                f"in {directory} for language {language}: "
                f"Expected {len(content.buttons)} or less, got {len(labels)}",
                file=sys.stderr,
            )
            sys.exit(1)
    for i, content_button in enumerate(content.buttons):
        yield NewsButton.from_content_button_and_translations(
            content_button,
            [
                (language, label[i])
                for language, label in translated_labels
                # There can be less labels, see the comment above.
                if i < len(label)
                # A translated label can be None/null when it has not been
                # translated yet, but e.g. a string after it is translated
                # (that is how Weblate handles it).
                if label[i] is not None and len(label[i]) > 0
            ],
        )


def ensure_translations(news_directory: str):
    translations_path = os.path.join(news_directory, TRANSLATIONS_DIR)
    if not os.path.exists(translations_path):
        print(f"Error: Missing translations for {news_directory}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(
        os.path.join(translations_path, TRANSLATIONS_DEFAULT_JSON_FILENAME)
    ):
        print(
            f"Error: Missing default translation for {news_directory}",
            file=sys.stderr,
        )
        sys.exit(1)


def enumerate_news() -> Iterator[News]:
    for news_id, directory in enumerate_news_directories():
        meta = read_news_meta(directory, META_VALIDATOR, META_SCHEMA_LOCATION)
        content_filepath = os.path.abspath(os.path.join(directory, CONTENT_FILENAME))
        content = parse_content_markdown(content_filepath)
        languages = get_languages(meta)
        ensure_translations(directory)
        yield News.create(
            id=news_id,
            meta=meta,
            content=content,
            directory=directory,
            languages=languages,
        )


def create_empty_directory(path):
    p = pathlib.Path(path)
    if p.exists():
        shutil.rmtree(p)
    p.mkdir(parents=True)


def clear_dist():
    create_empty_directory(DIST_LOCATION)


def export_to_dist(source_path: str, target_relative_path: str) -> None:
    if not os.path.exists(source_path):
        print(f"Error: Failed to export: {source_path} does not exist", file=sys.stderr)
        sys.exit(1)
    target_path = os.path.abspath(
        os.path.join(DIST_LOCATION, DIST_STATIC_DIR, target_relative_path)
    )
    if os.path.exists(target_path):
        print(f"Error: Failed to export: {target_path} already exists", file=sys.stderr)
        sys.exit(1)
    target_dirname = os.path.dirname(target_path)
    pathlib.Path(target_dirname).mkdir(parents=True)
    try:
        shutil.copyfile(source_path, target_path)
    except Exception as e:
        print(
            f"Error: Failed to export {source_path} to {target_relative_path}: {e}",
            file=sys.stderr,
        )
        sys.exit(1)


def url_for_dist_file(relative_path: str) -> str:
    return f"{URL_PROTOCOL}://{URL_DOMAIN}/{DIST_STATIC_DIR}/{relative_path}"


def enumerate_exported_news():
    for news in enumerate_news():
        new_banners = []
        for language, banner_path in news.banner.items():
            banner_filename = os.path.basename(banner_path)
            relative_path = (
                f"{DIST_STATIC_ASSETS_DIR}/{news.id}/{language}/{banner_filename}"
            )
            export_to_dist(banner_path, relative_path)
            banner_url = url_for_dist_file(relative_path)
            new_banners.append((language, banner_url))
        news.banner = dict(new_banners)
        yield news


def deep_walk_and_replace(data: Any, ref_replacer: Callable[[str], str]):
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "$ref":
                data[key] = ref_replacer(value)
            else:
                deep_walk_and_replace(value, ref_replacer)
    elif isinstance(data, list):
        for index, item in enumerate(data):
            deep_walk_and_replace(item, ref_replacer)


def export_schema(schema_validator: jsonschema.Validator, filename: str):
    schema = copy.deepcopy(schema_validator.schema)
    deep_walk_and_replace(
        schema, ref_replacer=lambda ref: url_for_dist_file(f"schemas/{ref}")
    )
    target_directory = os.path.join(DIST_LOCATION, DIST_STATIC_DIR, "schemas")
    pathlib.Path(target_directory).mkdir(parents=True, exist_ok=True)
    with open(os.path.join(target_directory, filename), "wt") as f:
        f.write(json.dumps(schema, indent=2))


def export_static_to_dist():
    for filename in os.listdir(STATIC_LOCATION):
        src_path = os.path.join(STATIC_LOCATION, filename)
        if os.path.isfile(src_path):
            dest_path = os.path.join(DIST_LOCATION, filename)
            shutil.copyfile(src_path, dest_path)


def export_schemas_to_dist():
    export_schema(LANGUAGES_VALIDATOR, LANGUAGES_SCHEMA_FILENAME)
    export_schema(META_VALIDATOR, META_SCHEMA_FILENAME)
    export_schema(NEWS_VALIDATOR, NEWS_SCHEMA_FILENAME)


def read_banner_strings(directory: str) -> str:
    banner_strings_filepath = os.path.join(
        directory, BANNER_DIR, BANNER_STRINGS_FILENAME
    )
    if not os.path.exists(banner_strings_filepath):
        print(
            f"Error: banner strings do not exist: {banner_strings_filepath}",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        with open(banner_strings_filepath, "rt") as f:
            banner_strings = f.read().strip()
    except Exception as e:
        print(
            f"Error: Failed to read banner strings: {banner_strings_filepath}",
            file=sys.stderr,
        )
        sys.exit(1)
    return banner_strings


def parse_content_markdown(markdown_filepath: str) -> Content:
    banner_strings = read_banner_strings(os.path.dirname(markdown_filepath))
    try:
        with open(markdown_filepath, "rt") as f:
            markdown_text = f.read()
    except Exception as e:
        print(
            f"Error: Failed to read markdown file: {markdown_filepath}",
            file=sys.stderr,
        )
        sys.exit(1)
    lines = []
    count = 0
    for line in markdown_text.split("\n"):
        empty = len(line.strip()) == 0
        if not empty:
            count += 1
        if count < 2 and empty:
            continue
        lines.append(line)
    result = {
        "banner_path": None,
        "banner_strings": banner_strings,
        "title": None,
        "content": None,
        "buttons": [],
    }
    if lines and (banner_match := re.match(r"!\[.*\]\((.+)\)", lines[0])):
        result["banner_path"] = banner_match.group(1).strip()
    if len(lines) > 1 and (title_match := re.match(r"##? (.+)", lines[1])):
        result["title"] = title_match.group(1).strip()
    if len(lines) > 2:
        content_lines = []
        is_button = False
        is_button_aside = False
        for line in lines[2:]:
            if re.match(r"<!--\s+button\s+-->", line, re.IGNORECASE):
                if is_button or is_button_aside:
                    print("Error: Button comment without button", file=sys.stderr)
                    sys.exit(1)
                is_button = True
                continue
            if re.match(r"<!--\s+button\s+aside\s+-->", line, re.IGNORECASE):
                if is_button or is_button_aside:
                    print("Error: Aside button comment without button", file=sys.stderr)
                    sys.exit(1)
                is_button_aside = True
                continue
            if is_button or is_button_aside:
                if len(line) == 0:
                    continue
                button_match = re.match(r"^\s*\[(.+)\]\((.+)\)\s*$", line)
                if button_match is None:
                    print(
                        f"Error: Button comment not followed by a link: {line}",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                button_text = button_match.group(1).strip()
                button_url = button_match.group(2).strip()
                try:
                    parsed_url = urllib.parse.urlparse(button_url)
                    if parsed_url.scheme == "https":
                        if not parsed_url.netloc:
                            raise ValueError("Invalid URL")
                    elif parsed_url.scheme == "mailto":
                        if not parsed_url.path:
                            raise ValueError("Invalid URL")
                    else:
                        raise ValueError("Invalid URL")
                except Exception as e:
                    print(f"Error: Invalid button URL: {button_url}", file=sys.stderr)
                    sys.exit(1)
                result["buttons"].append(
                    ContentButton(
                        aside=is_button_aside, label=button_text, url=button_url
                    )
                )
                is_button = False
                is_button_aside = False
                continue
            content_lines.append(line)
        result["content"] = "\n".join(content_lines).strip()
    content = Content(**result)
    if content.title is None:
        print(f"Error: title is empty in {markdown_filepath}", file=sys.stderr)
        sys.exit(1)
    if content.content is None:
        print(f"Error: content is empty in {markdown_filepath}", file=sys.stderr)
        sys.exit(1)
    if content.banner_path is None:
        print(f"Error: banner is empty in {markdown_filepath}", file=sys.stderr)
        sys.exit(1)
    content.banner_path = os.path.abspath(
        os.path.join(os.path.dirname(markdown_filepath), content.banner_path)
    )
    if not os.path.exists(content.banner_path):
        print(f"Error: banner does not exist: {content.banner_path}", file=sys.stderr)
        sys.exit(1)
    return content


@task
def translations(c: Context):
    for news_id, directory in enumerate_news_directories():
        meta = read_news_meta(directory, META_VALIDATOR, META_SCHEMA_LOCATION)
        content_filepath = os.path.abspath(os.path.join(directory, CONTENT_FILENAME))
        content = parse_content_markdown(content_filepath)
        translation = Translation.from_content(content)
        root_result = json.dumps(translation, default=encode_value, indent=4)
        translations_directory = os.path.join(os.path.join(directory, TRANSLATIONS_DIR))
        pathlib.Path(translations_directory).mkdir(parents=True, exist_ok=True)
        for language in get_languages(meta):
            language_filepath = os.path.join(translations_directory, f"{language}.json")
            to_write = json.dumps(dict())
            if language == DEFAULT_LANGUAGE_CODE:
                to_write = root_result
                if os.path.exists(language_filepath):
                    os.unlink(language_filepath)
            if not os.path.exists(language_filepath):
                with open(language_filepath, "wt") as f:
                    f.write(to_write)
                print(
                    f"Created {os.path.relpath(language_filepath, PWD)}",
                    file=sys.stderr,
                )


@task
def missing_banners(c: Context):
    for news_id, directory in enumerate_news_directories():
        meta = read_news_meta(directory, META_VALIDATOR, META_SCHEMA_LOCATION)
        for language in get_languages(meta):
            if not os.path.exists(
                os.path.join(directory, BANNER_DIR, language, BANNER_FILENAME)
            ):
                print(
                    f"Missing banner for news {news_id} and language '{language}'",
                    file=sys.stderr,
                )


# TODO pre-commit hook for calling `inv translations`


@task
def dist(c: Context):
    clear_dist()
    export_static_to_dist()
    export_schemas_to_dist()
    news = list(enumerate_exported_news())
    news = sorted(news, key=lambda n: n.id)
    root_dict = {
        "$schema": url_for_dist_file(f"schemas/news.schema.json"),
        "news": news,
    }
    result = json.dumps(root_dict, default=encode_value, separators=(",", ":"))
    result_pretty = json.dumps(root_dict, indent=2, default=encode_value)
    print(result_pretty)
    try:
        NEWS_VALIDATOR.validate(json.loads(result))
    except Exception as e:
        print(f"Error: Failed to validate generated news: {e}", file=sys.stderr)
        sys.exit(1)
    with open(os.path.join(DIST_LOCATION, DIST_STATIC_DIR, "news.min.json"), "wt") as f:
        f.write(result)
    with open(os.path.join(DIST_LOCATION, DIST_STATIC_DIR, "news.json"), "wt") as f:
        f.write(result_pretty)
