import os
import io
import logging
import json
import mimetypes
from http.server import SimpleHTTPRequestHandler, HTTPServer
from urllib.parse import urljoin
from urllib.parse import urlparse, unquote
from urllib.parse import urlunsplit
from xml.etree.ElementTree import Element, SubElement, tostring
logging.basicConfig(level=logging.DEBUG)

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

# Set default values if not provided in config or environment variables
config.setdefault("host", "127.0.0.1")
logging.info('host: {}'.format(config['host']))
config.setdefault("port", 8000)
logging.info('port: {}'.format(config['port']))
config.setdefault("directory", "podcasts")
logging.info('directory: {}'.format(config['directory']))
config.setdefault("subfolder", "")
logging.info('subfolder: {}'.format(config['subfolder']))

class RSSRequestHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        logging.info("requested path: {}".format(parsed_path))
        if parsed_path.path.startswith("/" + config['subfolder']):
            parsed_path = parsed_path._replace(path=parsed_path.path[len("/" + config['subfolder']):])
        if parsed_path.path.endswith(".rss"):
            folder_name = unquote(parsed_path.path[:-4]).lstrip('/')
            logging.info(folder_name)
            self.send_rss_feed(folder_name)
        else:
            super().do_GET()

    def send_rss_feed(self, folder_name):
        base_folder = os.path.join(os.getcwd(), config['directory'])
        folder_path = os.path.join(base_folder, folder_name)
        logging.info("folder_path: %s", folder_path)
        if os.path.isdir(folder_path):
            metadata_file = os.path.join(folder_path, "metadata.json")
            logging.info("metadata_file: %s", metadata_file)
            metadata = {}
            if os.path.exists(metadata_file):
                with open(metadata_file) as f:
                    metadata = json.load(f)
            logging.info("metadata: %s", metadata)
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
        SubElement(channel, "description").text = metadata.get("description", "")

        for filename in sorted(os.listdir(folder_path)):
            if not filename.endswith(".jpg"):
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
        item = Element("item")
        SubElement(item, "title").text = os.path.splitext(filename)[0]
        SubElement(item, "link").text = self.get_episode_link(folder_name, filename)
        SubElement(item, "enclosure", {
            "url": self.get_episode_link(folder_name, filename),
            "type": mimetypes.guess_type(filename)[0] or "application/octet-stream",
            "length": str(os.path.getsize(episode_path))
        })
        return item

    def get_episode_link(self, folder_name, filename):
        base_url = self.get_website_root()
        file_url = urljoin(base_url, f"{folder_name}/{filename}")
        return file_url

    def get_website_root(self):
        return urlunsplit(('http', f"{config['host']}:{config['port']}", f"/{config['subfolder']}", '', ''))

    def translate_path(self, path):
        return os.path.join(os.getcwd(), config["directory"], path[1:])

def main():
    server = HTTPServer((config["host"], int(config["port"])), RSSRequestHandler)
    print(f"Serving on http://{config['host']}:{config['port']}/{config['subfolder']}")
    server.serve_forever()

if __name__ == "__main__":
    main()
