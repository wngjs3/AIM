import requests


class CloudUploader:
    def __init__(self, api_url):
        self.api_url = api_url

    def upload(self, image_data, filename, user_info):
        """Implement cloud upload"""
        try:
            files = {"file": (filename, image_data, "image/jpeg")}

            storage_path = (
                f"captures/{user_info['name']}/{user_info['device_name']}/{filename}"
            )
            data = {
                "path": storage_path,
                "user_name": user_info["name"],
                "device_name": user_info["device_name"],
                "email": user_info.get("email", ""),
            }

            response = requests.post(self.api_url, files=files, data=data)

            if response.status_code == 200:
                return True, "Upload successful"
            return (
                False,
                f"Upload failed: {response.json().get('error', 'Unknown error')}",
            )

        except Exception as e:
            return False, f"Upload error: {str(e)}"
