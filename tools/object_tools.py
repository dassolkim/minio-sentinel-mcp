"""Object management tools for MinIO MCP Server."""

import logging
import json
import base64
from typing import Any, Dict, List, Optional
from fastmcp import FastMCP

from minio_client import MinIOClient, MinIOAPIError


logger = logging.getLogger(__name__)


def register_object_tools(mcp: FastMCP, client: MinIOClient) -> None:
    """Register object management tools with the MCP server."""

    @mcp.tool()
    async def minio_list_objects(bucket: str, prefix: str = "", limit: int = 100) -> str:
        """
        List objects in a MinIO bucket with optional prefix filtering.

        Args:
            bucket: Bucket name to list objects from
            prefix: Optional prefix to filter objects (default: empty, lists all)
            limit: Maximum number of objects to return (default: 100, max: 1000)

        Returns:
            Formatted list of objects with metadata
        """
        try:
            if not bucket:
                return "❌ Error: Bucket name is required"

            if limit < 1 or limit > 1000:
                return "❌ Error: limit must be between 1 and 1000"

            params = {"limit": limit}
            if prefix:
                params["prefix"] = prefix

            response = await client.get(f"/api/v1/buckets/{bucket}/objects", params=params)

            if response.success:
                objects_data = response.data

                if isinstance(objects_data, dict) and "data" in objects_data:
                    # MinIO REST API returns data in "data" field
                    objects = objects_data["data"]
                    # Get total count from meta information
                    meta = objects_data.get("meta", {})
                    total_count = meta.get("total_items", len(objects))
                elif isinstance(objects_data, dict) and "objects" in objects_data:
                    # Fallback for other API formats
                    objects = objects_data["objects"]
                    total_count = objects_data.get("total", len(objects))
                elif isinstance(objects_data, list):
                    objects = objects_data
                    total_count = len(objects)
                else:
                    return f"✅ No objects found in bucket '{bucket}'{f' with prefix \"{prefix}\"' if prefix else ''}"

                if not objects:
                    return f"✅ No objects found in bucket '{bucket}'{f' with prefix \"{prefix}\"' if prefix else ''}"

                # Format object list
                object_lines = []
                total_size = 0

                for obj in objects:
                    if isinstance(obj, dict):
                        name = obj.get("object_name", obj.get("name", obj.get("key", "unknown")))
                        size = obj.get("size", 0)
                        modified = obj.get("last_modified", obj.get("modified", "unknown"))
                        etag = obj.get("etag", "unknown")
                        content_type = obj.get("content_type", obj.get("mime_type", "unknown"))
                        is_dir = obj.get("is_dir", False)

                        # Convert size to readable format
                        if isinstance(size, (int, float)):
                            total_size += size
                            if size < 1024:
                                size_str = f"{size} B"
                            elif size < 1024 * 1024:
                                size_str = f"{size / 1024:.1f} KB"
                            elif size < 1024 * 1024 * 1024:
                                size_str = f"{size / (1024 * 1024):.1f} MB"
                            else:
                                size_str = f"{size / (1024 * 1024 * 1024):.2f} GB"
                        else:
                            size_str = str(size)

                        # Choose icon based on whether it's a directory or file
                        icon = "📁" if is_dir else "📄"
                        
                        object_lines.append(
                            f"  {icon} {name}\n"
                            f"    Size: {size_str}\n"
                            f"    Modified: {modified}\n"
                            f"    Content-Type: {content_type}\n"
                            f"    ETag: {etag[:16]}..." if len(str(etag)) > 16 else f"    ETag: {etag}"
                        )
                    else:
                        object_lines.append(f"  📄 {obj}")

                object_list = "\n".join(object_lines)

                # Format total size
                if total_size < 1024:
                    total_size_str = f"{total_size} B"
                elif total_size < 1024 * 1024:
                    total_size_str = f"{total_size / 1024:.1f} KB"
                elif total_size < 1024 * 1024 * 1024:
                    total_size_str = f"{total_size / (1024 * 1024):.1f} MB"
                else:
                    total_size_str = f"{total_size / (1024 * 1024 * 1024):.2f} GB"

                prefix_info = f" with prefix '{prefix}'" if prefix else ""

                return (
                    f"✅ Objects in bucket '{bucket}'{prefix_info} (showing {len(objects)} of {total_count}):\n"
                    f"{object_list}\n"
                    f"\n📊 Summary: {len(objects)} objects, Total size: {total_size_str}"
                    f"{f' (limited to {limit})' if len(objects) == limit else ''}"
                )

            else:
                if response.status_code == 404:
                    return f"❌ Bucket '{bucket}' not found"
                elif response.status_code == 403:
                    return f"❌ Access denied to bucket '{bucket}'"
                else:
                    return (
                        f"❌ Failed to list objects in bucket '{bucket}'\n"
                        f"Status: {response.status_code}\n"
                        f"Error: {response.error}"
                    )

        except MinIOAPIError as e:
            logger.error(f"List objects API error: {str(e)}")
            return f"❌ Failed to list objects: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error listing objects: {str(e)}")
            return f"❌ Unexpected error listing objects: {str(e)}"

    @mcp.tool()
    async def minio_upload_object(bucket: str, object_name: str, content: str, content_type: str = "text/plain") -> str:
        """
        Upload content to MinIO as an object.

        Args:
            bucket: Bucket name to upload to
            object_name: Name/key for the object in the bucket
            content: Content to upload (text content)
            content_type: MIME type of the content (default: text/plain)

        Returns:
            Upload status with object information
        """
        try:
            if not bucket:
                return "❌ Error: Bucket name is required"

            if not object_name:
                return "❌ Error: Object name is required"

            if not content:
                return "❌ Error: Content is required"

            # Prepare the content as multipart file upload
            content_bytes = content.encode('utf-8')

            # Split object_name into directory path and filename
            if '/' in object_name:
                # Extract directory path and filename
                path_parts = object_name.rsplit('/', 1)
                directory_path = path_parts[0] + '/'
                filename = path_parts[1]
            else:
                # No directory, just filename
                directory_path = ''
                filename = object_name

            # Create multipart files data
            files = {
                "file": (filename, content_bytes, content_type)
            }

            # Use directory path in URL parameter
            url_path = f"/api/v1/buckets/{bucket}/objects"
            if directory_path:
                url_path += f"?path={directory_path}"

            response = await client.post(url_path, files=files)

            if response.success:
                upload_info = response.data

                if isinstance(upload_info, dict):
                    # Parse response according to MinIO REST API format
                    obj_name = upload_info.get("object_name", upload_info.get("name", upload_info.get("key", object_name)))
                    size = upload_info.get("size", len(content_bytes))
                    etag = upload_info.get("etag", "unknown")
                    bucket_name = upload_info.get("bucket_name", bucket)
                    content_type_response = upload_info.get("content_type", content_type)

                    # Format size
                    if size < 1024:
                        size_str = f"{size} bytes"
                    elif size < 1024 * 1024:
                        size_str = f"{size / 1024:.1f} KB"
                    else:
                        size_str = f"{size / (1024 * 1024):.1f} MB"

                    return (
                        f"✅ Object uploaded successfully!\n"
                        f"Bucket: {bucket_name}\n"
                        f"Object: {obj_name}\n"
                        f"Size: {size_str}\n"
                        f"Content-Type: {content_type_response}\n"
                        f"ETag: {etag}\n"
                        f"Status: Upload complete"
                    )
                else:
                    return (
                        f"✅ Object '{object_name}' uploaded to bucket '{bucket}'!\n"
                        f"Size: {len(content_bytes)} bytes\n"
                        f"Content-Type: {content_type}"
                    )

            else:
                if response.status_code == 404:
                    return f"❌ Bucket '{bucket}' not found"
                elif response.status_code == 403:
                    return f"❌ Access denied to bucket '{bucket}'"
                elif response.status_code == 400:
                    return f"❌ Invalid object name or content"
                else:
                    return (
                        f"❌ Failed to upload object '{object_name}' to bucket '{bucket}'\n"
                        f"Status: {response.status_code}\n"
                        f"Error: {response.error}"
                    )

        except MinIOAPIError as e:
            logger.error(f"Upload object API error: {str(e)}")
            return f"❌ Failed to upload object: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error uploading object: {str(e)}")
            return f"❌ Unexpected error uploading object: {str(e)}"

    @mcp.tool()
    async def minio_download_object(bucket: str, object_name: str) -> str:
        """
        Download an object from MinIO bucket.

        Args:
            bucket: Bucket name to download from
            object_name: Name/key of the object to download

        Returns:
            Object content or download status
        """
        try:
            if not bucket:
                return "❌ Error: Bucket name is required"

            if not object_name:
                return "❌ Error: Object name is required"

            response = await client.get(f"/api/v1/buckets/{bucket}/objects/{object_name}")

            if response.success:
                content = response.data

                # Try to detect if content is text or binary
                if isinstance(content, str):
                    content_preview = content[:500] + "..." if len(content) > 500 else content
                    return (
                        f"✅ Object downloaded successfully!\n"
                        f"Bucket: {bucket}\n"
                        f"Object: {object_name}\n"
                        f"Size: {len(content)} characters\n"
                        f"Content Preview:\n"
                        f"─────────────────\n"
                        f"{content_preview}"
                    )
                elif isinstance(content, bytes):
                    # Try to decode as text
                    try:
                        text_content = content.decode('utf-8')
                        content_preview = text_content[:500] + "..." if len(text_content) > 500 else text_content
                        return (
                            f"✅ Object downloaded successfully!\n"
                            f"Bucket: {bucket}\n"
                            f"Object: {object_name}\n"
                            f"Size: {len(content)} bytes\n"
                            f"Content Preview (decoded):\n"
                            f"─────────────────\n"
                            f"{content_preview}"
                        )
                    except UnicodeDecodeError:
                        # Binary content
                        return (
                            f"✅ Binary object downloaded successfully!\n"
                            f"Bucket: {bucket}\n"
                            f"Object: {object_name}\n"
                            f"Size: {len(content)} bytes\n"
                            f"Content: Binary data (not displayable as text)\n"
                            f"Base64 Preview: {base64.b64encode(content[:100]).decode('ascii')}..."
                        )
                else:
                    return (
                        f"✅ Object downloaded successfully!\n"
                        f"Bucket: {bucket}\n"
                        f"Object: {object_name}\n"
                        f"Content: {content}"
                    )

            else:
                if response.status_code == 404:
                    return f"❌ Object '{object_name}' not found in bucket '{bucket}'"
                elif response.status_code == 403:
                    return f"❌ Access denied to object '{object_name}' in bucket '{bucket}'"
                else:
                    return (
                        f"❌ Failed to download object '{object_name}' from bucket '{bucket}'\n"
                        f"Status: {response.status_code}\n"
                        f"Error: {response.error}"
                    )

        except MinIOAPIError as e:
            logger.error(f"Download object API error: {str(e)}")
            return f"❌ Failed to download object: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error downloading object: {str(e)}")
            return f"❌ Unexpected error downloading object: {str(e)}"

    @mcp.tool()
    async def minio_get_object_info(bucket: str, object_name: str) -> str:
        """
        Get metadata information about an object without downloading it.

        Args:
            bucket: Bucket name containing the object
            object_name: Name/key of the object

        Returns:
            Object metadata including size, modification date, and headers
        """
        try:
            if not bucket:
                return "❌ Error: Bucket name is required"

            if not object_name:
                return "❌ Error: Object name is required"

            response = await client.head(f"/api/v1/buckets/{bucket}/objects/{object_name}")

            if response.success:
                # HEAD requests typically return metadata in headers, not body
                metadata = response.data if response.data else {}

                # For HEAD requests, useful info might be in the response object
                size = "unknown"
                content_type = "unknown"
                last_modified = "unknown"
                etag = "unknown"

                if hasattr(response, 'headers') and response.headers:
                    size = response.headers.get('content-length', 'unknown')
                    content_type = response.headers.get('content-type', 'unknown')
                    last_modified = response.headers.get('last-modified', 'unknown')
                    etag = response.headers.get('etag', 'unknown')

                if isinstance(metadata, dict):
                    size = metadata.get('size', metadata.get('content_length', size))
                    content_type = metadata.get('content_type', metadata.get('mime_type', content_type))
                    last_modified = metadata.get('last_modified', metadata.get('modified', last_modified))
                    etag = metadata.get('etag', etag)

                # Format size
                size_str = size
                if isinstance(size, (int, float)):
                    if size < 1024:
                        size_str = f"{size} bytes"
                    elif size < 1024 * 1024:
                        size_str = f"{size / 1024:.1f} KB"
                    elif size < 1024 * 1024 * 1024:
                        size_str = f"{size / (1024 * 1024):.1f} MB"
                    else:
                        size_str = f"{size / (1024 * 1024 * 1024):.2f} GB"

                return (
                    f"📄 Object Information: {object_name}\n"
                    f"═══════════════════════════════════\n"
                    f"Bucket: {bucket}\n"
                    f"Object: {object_name}\n"
                    f"Size: {size_str}\n"
                    f"Content-Type: {content_type}\n"
                    f"Last Modified: {last_modified}\n"
                    f"ETag: {etag}\n"
                    f"Status: Available"
                )

            else:
                if response.status_code == 404:
                    return f"❌ Object '{object_name}' not found in bucket '{bucket}'"
                elif response.status_code == 403:
                    return f"❌ Access denied to object '{object_name}' in bucket '{bucket}'"
                else:
                    return (
                        f"❌ Failed to get object info for '{object_name}' in bucket '{bucket}'\n"
                        f"Status: {response.status_code}\n"
                        f"Error: {response.error}"
                    )

        except MinIOAPIError as e:
            logger.error(f"Get object info API error: {str(e)}")
            return f"❌ Failed to get object info: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error getting object info: {str(e)}")
            return f"❌ Unexpected error getting object info: {str(e)}"

    @mcp.tool()
    async def minio_delete_object(bucket: str, object_name: str) -> str:
        """
        Delete an object from MinIO bucket.

        Args:
            bucket: Bucket name containing the object
            object_name: Name/key of the object to delete

        Returns:
            Deletion status
        """
        try:
            if not bucket:
                return "❌ Error: Bucket name is required"

            if not object_name:
                return "❌ Error: Object name is required"

            response = await client.delete(f"/api/v1/buckets/{bucket}/objects/{object_name}")

            if response.success:
                return (
                    f"✅ Object deleted successfully!\n"
                    f"Bucket: {bucket}\n"
                    f"Object: {object_name}\n"
                    f"Status: Object has been permanently removed"
                )

            else:
                if response.status_code == 404:
                    return f"❌ Object '{object_name}' not found in bucket '{bucket}'"
                elif response.status_code == 403:
                    return f"❌ Access denied: Cannot delete object '{object_name}' from bucket '{bucket}'"
                else:
                    return (
                        f"❌ Failed to delete object '{object_name}' from bucket '{bucket}'\n"
                        f"Status: {response.status_code}\n"
                        f"Error: {response.error}"
                    )

        except MinIOAPIError as e:
            logger.error(f"Delete object API error: {str(e)}")
            return f"❌ Failed to delete object: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error deleting object: {str(e)}")
            return f"❌ Unexpected error deleting object: {str(e)}"

    @mcp.tool()
    async def minio_copy_object(src_bucket: str, src_object: str, dst_bucket: str, dst_object: str) -> str:
        """
        Copy an object from one location to another within MinIO.

        Args:
            src_bucket: Source bucket name
            src_object: Source object name/key
            dst_bucket: Destination bucket name
            dst_object: Destination object name/key

        Returns:
            Copy operation status
        """
        try:
            if not all([src_bucket, src_object, dst_bucket, dst_object]):
                return "❌ Error: All parameters (source bucket, source object, destination bucket, destination object) are required"

            copy_data = {
                "source": {
                    "bucket": src_bucket,
                    "object": src_object
                },
                "destination": {
                    "bucket": dst_bucket,
                    "object": dst_object
                }
            }

            response = await client.post(f"/api/v1/buckets/{dst_bucket}/objects/copy", json_data=copy_data)

            if response.success:
                copy_info = response.data

                if isinstance(copy_info, dict):
                    size = copy_info.get("size", "unknown")
                    etag = copy_info.get("etag", "unknown")

                    return (
                        f"✅ Object copied successfully!\n"
                        f"Source: {src_bucket}/{src_object}\n"
                        f"Destination: {dst_bucket}/{dst_object}\n"
                        f"Size: {size}\n"
                        f"ETag: {etag}\n"
                        f"Status: Copy complete"
                    )
                else:
                    return (
                        f"✅ Object copied successfully!\n"
                        f"Source: {src_bucket}/{src_object}\n"
                        f"Destination: {dst_bucket}/{dst_object}"
                    )

            else:
                if response.status_code == 404:
                    return f"❌ Source object '{src_object}' not found in bucket '{src_bucket}' or destination bucket '{dst_bucket}' not found"
                elif response.status_code == 403:
                    return f"❌ Access denied: Insufficient permissions for copy operation"
                elif response.status_code == 409:
                    return f"❌ Destination object '{dst_object}' already exists in bucket '{dst_bucket}'"
                else:
                    return (
                        f"❌ Failed to copy object\n"
                        f"Status: {response.status_code}\n"
                        f"Error: {response.error}"
                    )

        except MinIOAPIError as e:
            logger.error(f"Copy object API error: {str(e)}")
            return f"❌ Failed to copy object: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error copying object: {str(e)}")
            return f"❌ Unexpected error copying object: {str(e)}"

    @mcp.tool()
    async def minio_bulk_delete(bucket: str, object_names: List[str]) -> str:
        """
        Delete multiple objects from a bucket in a single operation.

        Args:
            bucket: Bucket name containing the objects
            object_names: List of object names/keys to delete

        Returns:
            Bulk deletion status with details for each object
        """
        try:
            if not bucket:
                return "❌ Error: Bucket name is required"

            if not object_names or not isinstance(object_names, list):
                return "❌ Error: Object names list is required"

            if len(object_names) > 1000:
                return "❌ Error: Cannot delete more than 1000 objects in a single request"

            delete_data = {
                "objects": [{"name": name} for name in object_names]
            }

            response = await client.post(f"/api/v1/buckets/{bucket}/objects/bulk-delete", json_data=delete_data)

            if response.success:
                delete_info = response.data

                if isinstance(delete_info, dict):
                    deleted = delete_info.get("deleted", [])
                    errors = delete_info.get("errors", [])

                    result_lines = [f"✅ Bulk delete operation completed!"]
                    result_lines.append(f"Bucket: {bucket}")

                    if deleted:
                        result_lines.append(f"\n🗑️ Successfully deleted ({len(deleted)}):")
                        for obj in deleted[:10]:  # Show first 10
                            obj_name = obj.get("name") if isinstance(obj, dict) else str(obj)
                            result_lines.append(f"  ✅ {obj_name}")
                        if len(deleted) > 10:
                            result_lines.append(f"  ... and {len(deleted) - 10} more objects")

                    if errors:
                        result_lines.append(f"\n❌ Failed to delete ({len(errors)}):")
                        for error in errors[:5]:  # Show first 5 errors
                            if isinstance(error, dict):
                                obj_name = error.get("name", "unknown")
                                error_msg = error.get("error", "unknown error")
                                result_lines.append(f"  ❌ {obj_name}: {error_msg}")
                            else:
                                result_lines.append(f"  ❌ {error}")
                        if len(errors) > 5:
                            result_lines.append(f"  ... and {len(errors) - 5} more errors")

                    result_lines.append(f"\n📊 Summary: {len(deleted)} deleted, {len(errors)} failed")

                    return "\n".join(result_lines)
                else:
                    return (
                        f"✅ Bulk delete operation completed!\n"
                        f"Bucket: {bucket}\n"
                        f"Objects: {len(object_names)} objects processed"
                    )

            else:
                if response.status_code == 404:
                    return f"❌ Bucket '{bucket}' not found"
                elif response.status_code == 403:
                    return f"❌ Access denied to bucket '{bucket}'"
                else:
                    return (
                        f"❌ Failed to perform bulk delete in bucket '{bucket}'\n"
                        f"Status: {response.status_code}\n"
                        f"Error: {response.error}"
                    )

        except MinIOAPIError as e:
            logger.error(f"Bulk delete API error: {str(e)}")
            return f"❌ Failed to perform bulk delete: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error during bulk delete: {str(e)}")
            return f"❌ Unexpected error during bulk delete: {str(e)}"

    @mcp.tool()
    async def minio_generate_presigned(bucket: str, object_name: str, expires_in: int = 3600) -> str:
        """
        Generate a presigned URL for temporary access to an object.

        Args:
            bucket: Bucket name containing the object
            object_name: Object name/key
            expires_in: URL expiration time in seconds (default: 3600, max: 604800)

        Returns:
            Presigned URL and expiration information
        """
        try:
            if not bucket:
                return "❌ Error: Bucket name is required"

            if not object_name:
                return "❌ Error: Object name is required"

            if expires_in < 1 or expires_in > 604800:  # Max 7 days
                return "❌ Error: Expiration time must be between 1 second and 604800 seconds (7 days)"

            presign_data = {
                "bucket": bucket,
                "object": object_name,
                "expires_in": expires_in
            }

            response = await client.post(f"/api/v1/buckets/{bucket}/objects/presigned", json_data=presign_data)

            if response.success:
                presign_info = response.data

                if isinstance(presign_info, dict):
                    url = presign_info.get("url", "unknown")
                    expires_at = presign_info.get("expires_at", "unknown")

                    # Format expiration time
                    if expires_in < 60:
                        expire_str = f"{expires_in} seconds"
                    elif expires_in < 3600:
                        expire_str = f"{expires_in // 60} minutes"
                    elif expires_in < 86400:
                        expire_str = f"{expires_in // 3600} hours"
                    else:
                        expire_str = f"{expires_in // 86400} days"

                    return (
                        f"✅ Presigned URL generated successfully!\n"
                        f"Bucket: {bucket}\n"
                        f"Object: {object_name}\n"
                        f"Expires in: {expire_str}\n"
                        f"Expires at: {expires_at}\n"
                        f"\n🔗 Presigned URL:\n{url}\n"
                        f"\n⚠️ Note: This URL provides temporary access to the object. Keep it secure!"
                    )
                else:
                    return (
                        f"✅ Presigned URL generated!\n"
                        f"URL: {presign_info}\n"
                        f"Expires in: {expires_in} seconds"
                    )

            else:
                if response.status_code == 404:
                    return f"❌ Object '{object_name}' not found in bucket '{bucket}'"
                elif response.status_code == 403:
                    return f"❌ Access denied to object '{object_name}' in bucket '{bucket}'"
                else:
                    return (
                        f"❌ Failed to generate presigned URL\n"
                        f"Status: {response.status_code}\n"
                        f"Error: {response.error}"
                    )

        except MinIOAPIError as e:
            logger.error(f"Generate presigned URL API error: {str(e)}")
            return f"❌ Failed to generate presigned URL: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error generating presigned URL: {str(e)}")
            return f"❌ Unexpected error generating presigned URL: {str(e)}"