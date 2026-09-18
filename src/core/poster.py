"""Poster download and upload functionality for Douban/IMDb posters."""

import os
import tempfile
from pathlib import Path
from typing import Optional, Tuple

import requests

from src.core.picturebed import upload_picture


def get_poster_url_from_data(data: dict) -> str:
    """
    Extract poster URL from PT-Gen API response data.
    
    Args:
        data: PT-Gen API response dictionary
        
    Returns:
        Poster URL string, or empty string if not found
    """
    # PT-Gen API may return poster in different fields
    # Common fields: 'poster', 'img', 'image', 'cover'
    possible_fields = ['poster', 'img', 'image', 'cover', 'posterUrl']
    
    for field in possible_fields:
        if field in data and data[field]:
            poster_url = data[field]
            print(f'Found poster URL in field "{field}": {poster_url}')
            return poster_url
    
    # Check nested data structure
    if 'data' in data:
        for field in possible_fields:
            if field in data['data'] and data['data'][field]:
                poster_url = data['data'][field]
                print(f'Found poster URL in nested field "data.{field}": {poster_url}')
                return poster_url
    
    print('No poster URL found in PT-Gen response')
    return ''


def download_poster(poster_url: str, save_path: str) -> Tuple[bool, str]:
    """
    Download poster image from URL to specified path.
    
    Args:
        poster_url: URL of the poster image
        save_path: Local path to save the poster
        
    Returns:
        Tuple of (success: bool, message/path: str)
    """
    try:
        if not poster_url:
            return False, 'Poster URL is empty'
        
        print(f'Starting poster download from: {poster_url}')
        
        # Headers to bypass anti-spider protection (especially for Douban)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh-TW;q=0.7,zh;q=0.6',
            'Referer': 'https://movie.douban.com/',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Fetch-Dest': 'image',
            'Sec-Fetch-Mode': 'no-cors',
            'Sec-Fetch-Site': 'cross-site',
        }
        
        # Send GET request to download the image with headers
        response = requests.get(poster_url, headers=headers, timeout=30, stream=True)
        
        if response.status_code != 200:
            return False, f'Failed to download poster, status code: {response.status_code}'
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        # Write the image to file
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        print(f'Poster downloaded successfully to: {save_path}')
        return True, save_path
        
    except requests.Timeout:
        print('Poster download timeout')
        return False, 'Poster download timeout (30s)'
        
    except requests.RequestException as e:
        print(f'Poster download request error: {e}')
        return False, f'Poster download request error: {str(e)}'
        
    except IOError as e:
        print(f'Failed to save poster file: {e}')
        return False, f'Failed to save poster file: {str(e)}'
        
    except Exception as e:
        print(f'Unexpected error during poster download: {e}')
        return False, f'Unexpected error: {str(e)}'


def process_poster(
    poster_url: str,
    picture_bed_api_url: str,
    picture_bed_api_token: str,
    temp_dir: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Download poster, upload to image hosting, and clean up temporary file.

    Main orchestration function that:
    1. Downloads the poster from Douban/IMDb
    2. Uploads it to the configured image hosting service
    3. Deletes the temporary file (only on success)
    4. Returns the uploaded image URL

    Args:
        poster_url: URL of the poster image from Douban/IMDb
        picture_bed_api_url: Image hosting API URL
        picture_bed_api_token: Image hosting API token
        temp_dir: Temporary directory for downloads (optional)

    Returns:
        Tuple of (success: bool, uploaded_url_or_error: str)
    """
    temp_file_path = None
    upload_success = False

    try:
        # Use provided temp_dir or create one
        if temp_dir is None:
            temp_dir = tempfile.gettempdir()

        # Create a unique temporary file path
        temp_file_path = os.path.join(temp_dir, f'poster_{id(poster_url)}.jpg')

        print('=== Starting poster processing ===')
        print(f'Poster URL: {poster_url}')
        print(f'Temp file path: {temp_file_path}')

        # Step 1: Download the poster
        download_success, download_result = download_poster(poster_url, temp_file_path)

        if not download_success:
            return False, f'Failed to download poster: {download_result}'

        # Print file size for debugging
        file_size = os.path.getsize(temp_file_path)
        print(f'Downloaded poster file size: {file_size} bytes')

        # Step 2: Upload to image hosting
        print('Uploading poster to image hosting service...')
        upload_success, upload_result = upload_picture(
            picture_bed_api_url,
            picture_bed_api_token,
            temp_file_path
        )

        if not upload_success:
            print(f'Upload failed. Temp file kept for debugging: {temp_file_path}')
            print(f'Temp file size: {file_size} bytes')
            return False, f'Failed to upload poster: {upload_result}'

        print(f'Poster uploaded successfully: {upload_result}')

        # upload_result is in BBCode format: [img]url[/img]
        # Extract the URL
        if upload_result.startswith('[img]') and upload_result.endswith('[/img]'):
            uploaded_url = upload_result[5:-6]  # Remove [img] and [/img]
        else:
            uploaded_url = upload_result

        return True, uploaded_url

    except Exception as e:
        print(f'Error during poster processing: {e}')
        return False, f'Error during poster processing: {str(e)}'

    finally:
        # Step 3: Clean up temporary file only on successful upload
        if upload_success and temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                print(f'Temporary poster file deleted: {temp_file_path}')
            except Exception as e:
                print(f'Warning: Failed to delete temporary poster file: {e}')


def get_poster_from_pt_gen_response(
    pt_gen_data: dict,
    picture_bed_api_url: str,
    picture_bed_api_token: str,
    temp_dir: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Convenience function to extract poster from PT-Gen response and process it.
    
    Args:
        pt_gen_data: Full PT-Gen API response data
        picture_bed_api_url: Image hosting API URL
        picture_bed_api_token: Image hosting API token
        temp_dir: Temporary directory for downloads (optional)
        
    Returns:
        Tuple of (success: bool, uploaded_url_or_error: str)
    """
    poster_url = get_poster_url_from_data(pt_gen_data)
    
    if not poster_url:
        return False, 'No poster URL found in PT-Gen response'
    
    return process_poster(poster_url, picture_bed_api_url, picture_bed_api_token, temp_dir)
