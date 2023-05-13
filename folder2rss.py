import os
import re
import io
import logging
import json
import mimetypes
from http.server import SimpleHTTPRequestHandler, HTTPServer
from urllib.parse import urljoin
from urllib.parse import urlparse, unquote
from urllib.parse import urlunsplit
from xml.etree.ElementTree import Element, SubElement, tostring

# Load configuration
CONFIG_FILE = "config.json"
ENV_PREFIX = "RSS_SERVER_"
config = {}

if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE) as f:
        config = json.load(f)

for key, value in os.environ.items():
    if key.startswith(ENV_PREFIX):
        config_key = key[len(ENV_PREFIX):].lower()
        config[config_key] = value

config.setdefault("loglevel", "INFO")

def get_logging_config(log_level):
    log_level_dict = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    return log_level_dict[log_level]

logging.basicConfig(level=get_logging_config(config['loglevel']))
logging.info('loglevel: {}'.format(config['loglevel']))

# Set default values if not provided in config or environment variables
config.setdefault("scheme", "http")
logging.info('scheme: {}'.format(config['scheme']))
config.setdefault("port", 8000)
logging.info('host: {}'.format(config['host']))
config.setdefault("port", 8000)
logging.info('port: {}'.format(config['port']))
config.setdefault("directory", "podcasts")
logging.info('directory: {}'.format(config['directory']))
config.setdefault("subfolder", "")
logging.info('subfolder: {}'.format(config['subfolder']))

class RSSRequestHandler(SimpleHTTPRequestHandler):

    def list_directory(self, path) -> io.BytesIO | None:
        return


    def do_GET(self):
        parsed_path = urlparse(self.path)
        logging.info("requested path: {}".format(parsed_path))
        if parsed_path.path.startswith("/" + config['subfolder']):
            parsed_path = parsed_path._replace(path=parsed_path.path[len("/" + config['subfolder']):])
        if parsed_path.path.endswith(".rss"):
            folder_name = unquote(parsed_path.path[:-4]).lstrip('/')
            self.send_rss_feed(folder_name)
        else:
            super().do_GET()

    def send_rss_feed(self, folder_name):
        base_folder = os.path.join(os.getcwd(), config['directory'])
        folder_path = os.path.join(base_folder, folder_name)
        if os.path.isdir(folder_path):
            metadata_file = os.path.join(folder_path, "metadata.json")
            metadata = {}
            if os.path.exists(metadata_file):
                with open(metadata_file) as f:
                    metadata = json.load(f)
            rss = self.create_rss_feed(folder_name, folder_path, metadata)
            self.send_response(200)
            self.send_header("Content-Type", "application/xml")
            self.end_headers()
            self.wfile.write(tostring(rss))
        else:
            self.send_error(404, "Not Found")

    def create_rss_feed(self, folder_name, folder_path, metadata):
        rss = Element("{http://www.itunes.com/dtds/podcast-1.0.dtd}rss", {"version": "2.0", "xmlns:itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd"})
        channel = SubElement(rss, "channel")
        SubElement(channel, "itunes:block").text = "yes"
        SubElement(channel, "title").text = metadata.get("title", folder_name)
        SubElement(channel, "link").text = self.get_podcast_link(folder_name)
        SubElement(channel, "itunes:image", href=self.get_pod_thumb_link(folder_name))
        SubElement(channel, "description").text = metadata.get("description", "")

        for filename in sorted(os.listdir(folder_path)):
            if not filename.endswith(".jpg") and not filename.endswith(".json") and not filename.endswith(".png"):
                episode_path = os.path.join(folder_path, filename)
                if os.path.isfile(episode_path):
                    item = self.create_rss_item(folder_name, episode_path, filename)
                    channel.append(item)

        return rss

    def get_podcast_link(self, folder_name):
        base_url = self.get_website_root()
        folder_url = urljoin(base_url, f"{folder_name}")
        return folder_url

    def create_rss_item(self, folder_name, episode_path, filename):
        # to add a duration just add to the file name this pattern _%_hh:mm:ss_%_
        duration_pattern = r'___(\d{1,2}:\d{2}:\d{2})___'
        match = re.search(duration_pattern, episode_path)
        time_str = "00:00:00"
        if match:
            time_str = match.group(1)
        item = Element("item")
        SubElement(item, "title").text = os.path.splitext(filename)[0]
        SubElement(item, "link").text = self.get_episode_link(folder_name, filename)
        SubElement(item, "enclosure", {
            "url": self.get_episode_link(folder_name, filename),
            "type": mimetypes.guess_type(filename)[0] or "application/octet-stream",
            "length": str(os.path.getsize(episode_path))
        })
        SubElement(item, "thumbnail").text = self.get_episode_thumb_link(folder_name, filename)
        SubElement(item, "itunes:duration").text = time_str

        return item

    def get_pod_thumb_link(self, folder_name):
        base_url = self.get_website_root()
        file_url = urljoin(base_url, f"{folder_name}/thumbnail.png")
        return file_url

    def get_episode_thumb_link(self, folder_name, filename):
        base_url = self.get_website_root()
        file_url = urljoin(base_url, f"{folder_name}/{os.path.splitext(filename)[0]}.jpg")
        return file_url

    def get_episode_link(self, folder_name, filename):
        base_url = self.get_website_root()
        logging.debug(f"Base URL: {base_url}")
        file_url = urljoin(base_url, f"{folder_name}/{filename}")
        logging.debug(f"relative File URL: "+ f"{folder_name}/{filename}")
        logging.debug(f"File URL: {file_url}")
        return file_url

    def get_website_root(self):
        base = urlunsplit((f"{config['scheme']}", f"{config['host']}:{config['port']}", '', '', ''))
        if config['subfolder'] != "":
            base = urljoin(base, config['subfolder'])
        return base +"/"

    def translate_path(self, path):
        new_path = path
        if config['subfolder'] != "":
            new_path = path.replace("/" + config['subfolder'], "")
        final_path = os.path.join(os.getcwd(), config["directory"], new_path[1:])
        if not os.path.abspath(final_path).startswith(os.getcwd()):
            return None
        return final_path

def main():
    server = HTTPServer(("0.0.0.0", int(8000)), RSSRequestHandler)
    print(f"Serving on http://{config['host']}:{config['port']}/{config['subfolder']}")
    server.serve_forever()

if __name__ == "__main__":
    main()
