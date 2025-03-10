import os
import requests
import base64
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class GitHubPublisher:
    def __init__(self, token):
        self.token = token
        self.api_base = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }

    def create_repo(self, name, description="Video Analysis System"):
        """Create a new GitHub repository"""
        try:
            url = f"{self.api_base}/user/repos"
            data = {
                "name": name,
                "description": description,
                "private": False,
                "auto_init": False
            }
            response = requests.post(url, headers=self.headers, json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error creating repository: {str(e)}")
            raise

    def upload_file(self, repo_name, file_path, commit_message="Initial commit"):
        """Upload a file to the repository"""
        try:
            with open(file_path, 'rb') as file:
                content = file.read()
                content_b64 = base64.b64encode(content).decode('utf-8')

            url = f"{self.api_base}/repos/{self.get_user()['login']}/{repo_name}/contents/{Path(file_path).name}"
            data = {
                "message": commit_message,
                "content": content_b64
            }
            
            response = requests.put(url, headers=self.headers, json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error uploading file {file_path}: {str(e)}")
            raise

    def get_user(self):
        """Get authenticated user information"""
        try:
            response = requests.get(f"{self.api_base}/user", headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting user info: {str(e)}")
            raise

def publish_to_github(repo_name="video-analysis-system"):
    """Publish all project files to GitHub"""
    try:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise ValueError("GitHub token not found in environment variables")

        publisher = GitHubPublisher(token)
        
        # Create repository
        repo = publisher.create_repo(repo_name)
        logger.info(f"Created repository: {repo['html_url']}")

        # Files to upload
        files = [
            "main.py",
            "video_processor.py",
            "ai_analyzer.py",
            "github_publisher.py",
            "README.md",
            "CONTRIBUTING.md",
            "CONTRIBUTORS.md",
            ".gitignore"
        ]

        # Upload each file
        for file in files:
            if os.path.exists(file):
                publisher.upload_file(repo_name, file)
                logger.info(f"Uploaded {file}")

        return repo['html_url']

    except Exception as e:
        logger.error(f"Error publishing to GitHub: {str(e)}")
        raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    url = publish_to_github()
    print(f"Repository published at: {url}")
