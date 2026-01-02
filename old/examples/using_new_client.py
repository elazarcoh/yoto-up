"""
Example: Using the new YotoApiClient

This example demonstrates how to use the production-ready Yoto API client.
"""

import asyncio
from pathlib import Path

from yoto_up.yoto_api_client import (
    YotoApiClient,
    YotoApiConfig,
    YotoAuthError,
    YotoApiError,
)


async def main():
    """Example usage of YotoApiClient"""
    
    # Configure the client
    config = YotoApiConfig(
        client_id="your_client_id_here",
        timeout=30.0,
        max_retries=3,
    )
    
    # Token storage path
    token_file = Path.home() / ".yoto" / "tokens.json"
    
    # Create and use the client
    async with YotoApiClient(config, token_file=token_file) as client:
        
        # Authenticate if needed
        if not client.is_authenticated():
            print("Not authenticated. Starting authentication flow...")
            try:
                await client.authenticate(
                    callback=lambda url, code: print(f"\nVisit: {url}\nCode: {code}\n"),
                    timeout=300,
                )
                print("✅ Authentication successful!")
            except YotoAuthError as e:
                print(f"❌ Authentication failed: {e}")
                return
        
        try:
            # Get all user's content
            print("\n📚 Fetching your content...")
            cards = await client.get_my_content()
            print(f"Found {len(cards)} cards:")
            for card in cards[:5]:  # Show first 5
                print(f"  - {card.title} (ID: {card.id})")
            
            # Create a new card
            print("\n✨ Creating new playlist...")
            new_card = await client.create_card(
                title="My Test Playlist",
                content={"chapters": []},
                metadata={"description": "Created with new API client"},
            )
            print(f"✅ Created card: {new_card.title} (ID: {new_card.id})")
            
            # Upload a cover image (if you have one)
            cover_path = Path("path/to/cover.jpg")
            if cover_path.exists():
                print("\n🖼️ Uploading cover image...")
                cover_response = await client.upload_cover_image(
                    image_path=cover_path,
                    autoconvert=True,
                )
                print(f"✅ Uploaded cover: {cover_response.cover_image}")
                
                # Update card with cover
                new_card.metadata = new_card.metadata or {}
                new_card.metadata["cover"] = cover_response.cover_image
                updated_card = await client.update_card(new_card)
                print("✅ Card updated with cover")
            
            # Get devices
            print("\n📱 Fetching devices...")
            devices = await client.get_devices()
            print(f"Found {len(devices)} devices:")
            for device in devices:
                print(f"  - {device.name} ({device.id})")
            
            # Example: Upload audio file
            audio_file = Path("path/to/audio.mp3")
            if audio_file.exists():
                print(f"\n🎵 Processing audio file: {audio_file.name}")
                
                # Calculate hash
                sha256, audio_bytes = client.calculate_sha256(audio_file)
                print(f"  SHA-256: {sha256[:16]}...")
                
                # Get upload URL
                upload_response = await client.get_audio_upload_url(
                    sha256=sha256,
                    filename=audio_file.name,
                )
                
                if upload_response.upload.upload_url:
                    # File doesn't exist, need to upload
                    print("  Uploading audio...")
                    await client.upload_audio_file(
                        upload_url=upload_response.upload.upload_url,
                        audio_bytes=audio_bytes,
                    )
                    print("  ✅ Audio uploaded")
                else:
                    print("  ℹ️ File already exists on server")
                
                # Wait for transcoding
                print("  Waiting for transcoding...")
                transcoded = await client.poll_for_transcoding(
                    upload_id=upload_response.upload.upload_id,
                    loudnorm=False,
                    poll_interval=2.0,
                    max_attempts=60,
                    callback=lambda attempt, max_attempts: print(f"    Attempt {attempt}/{max_attempts}"),
                )
                print(f"  ✅ Transcoded: {transcoded.audio.url}")
                print(f"     Duration: {transcoded.audio.duration}s")
                print(f"     Size: {transcoded.audio.size} bytes")
        
        except YotoApiError as e:
            print(f"\n❌ API Error: {e}")
            raise
        
        print("\n✅ All done!")


if __name__ == "__main__":
    asyncio.run(main())
