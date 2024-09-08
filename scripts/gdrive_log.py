from pathlib import Path

from defaults import HUMAN_ADDRESS, LOG_FOLDER_NAME, SERVICE_ACCOUNT_FILE

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def create_folder(service, name):
    """Create a new folder in Google Drive."""
    file_metadata = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    file = service.files().create(body=file_metadata, fields="id").execute()
    return file.get("id")


# Share the file with your personal account
def share_file(service, file_id, email_address):
    """Create a permission for an email address."""
    permissions = {"type": "user", "role": "reader", "emailAddress": email_address}
    service.permissions().create(
        fileId=file_id,
        body=permissions,
        fields="id",
    ).execute()


def find_folder(service, folder_name):
    """Find a folder by its name."""
    query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    results = (
        service.files()
        .list(q=query, spaces="drive", fields="files(id, name)")
        .execute()
    )
    folders = results.get("files", [])

    if not folders:
        print("No folders found.")
        return None
    else:
        print("Folders:")
        for folder in folders:
            print(f"{folder['name']} ({folder['id']})")
        return [
            folder["id"] for folder in folders
        ]  # Return the ID of the first matching folder


def share_folder(service, folder_id, email_address):
    """Share the folder with a user via their email."""
    permissions = {
        "type": "user",
        "role": "reader",  # or 'writer' for editable access
        "emailAddress": email_address,
    }
    service.permissions().create(
        fileId=folder_id,
        body=permissions,
        fields="id",
    ).execute()


def check_folder_shared(service, folder_id, email_address):
    """Check if a folder is shared with a specific email address."""
    permissions = (
        service.permissions()
        .list(fileId=folder_id, fields="permissions(emailAddress, role)")
        .execute()
    )
    for permission in permissions.get("permissions", []):
        if permission.get("emailAddress") == email_address:
            print(
                f"Folder is shared with {email_address} with role: {permission.get('role')}"
            )
            return True
    print("Folder is not shared with the specified email.")
    return False


def delete_folder(service, folder_id):
    """Delete a folder from Google Drive by its ID."""
    try:
        service.files().delete(fileId=folder_id).execute()
        print(f"Folder with ID {folder_id} was deleted successfully.")

    except Exception as e:
        print(f"An error occurred: {e}")


def upload_file(service, file_path, folder_id=None):
    """Upload a file to Google Drive."""
    # Upload a file to the greg_logs folder
    file_metadata = {"name": file_path.name}
    if folder_id:
        file_metadata["parents"] = [folder_id]

    media = MediaFileUpload(file_path, mimetype="text/csv")
    file = (
        service.files()
        .create(body=file_metadata, media_body=media, fields="id")
        .execute()
    )
    return file.get("id")


class GDriveLogger:
    SCOPES = ["https://www.googleapis.com/auth/drive"]
    SERVICE_ACCOUNT_FILE = SERVICE_ACCOUNT_FILE

    LOG_FOLDER_NAME = LOG_FOLDER_NAME
    HUMAN_ADDRESS = HUMAN_ADDRESS

    def __init__(self):
        # Setup the Drive v3 API
        credentials = Credentials.from_service_account_file(
            self.SERVICE_ACCOUNT_FILE, scopes=self.SCOPES
        )

        self.service = build("drive", "v3", credentials=credentials)

        # Find folder id:
        ids = find_folder(self.service, self.LOG_FOLDER_NAME)
        if not ids:
            self.folder_id = create_folder(self.service, self.LOG_FOLDER_NAME)
        elif len(ids) > 1:
            raise ValueError(
                f"Multiple folders with name {self.LOG_FOLDER_NAME} found. Please delete the duplicates."
            )
        else:
            self.folder_id = ids[0]

        # Check if folder is shared:
        if not check_folder_shared(self.service, self.folder_id, self.HUMAN_ADDRESS):
            share_folder(self.service, self.folder_id, self.HUMAN_ADDRESS)

    def upload(self, file_path):
        upload_file(self.service, file_path, self.folder_id)


if __name__ == "__main__":
    # test the GDriveLogger class:
    filename = Path("/path/to/test.csv")

    # Replace 'your_email@example.com' with your personal Google account email
    gdrive_backup = GDriveLogger()
    gdrive_backup.upload(filename)
