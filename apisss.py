from flask import Flask, request, render_template, Response
import yt_dlp
import re
import unicodedata
import browser_cookie3  # Çerezleri almak için
import tempfile         # Geçici dosya oluşturmak için
import os
from urllib.parse import quote  # Unicode karakterler için encode işlemi

app = Flask(__name__)

@app.route('/')
def index():
    # Ana arama ve indirme sayfasını gösterir
    return render_template('index.html')

@app.route('/process', methods=['GET'])
def process():
    query = request.args.get('query')
    if not query:
        return "No input provided", 400

    # Kullanıcının bir YouTube linki mi yoksa arama sorgusu mu girdiğini kontrol et
    if "youtube.com" in query or "youtu.be" in query:
        # Kullanıcı bir link yapıştırdıysa, doğrudan indirme sayfasına yönlendir
        return download_video(query)
    else:
        # Kullanıcı bir anahtar kelime girdi; arama sonuçlarını döndür
        return search_videos(query)

def get_cookiefile():
    """browser_cookie3 çerezlerini Netscape formatına dönüştür ve geçici dosyaya kaydet."""
    cookies = browser_cookie3.firefox(domain_name="youtube.com")  # Firefox için
    # Eğer Chrome kullanıyorsanız: browser_cookie3.chrome(domain_name="youtube.com")

    # Netscape formatında çerez dosyası oluştur
    temp_cookiefile = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
    with open(temp_cookiefile.name, 'w') as f:
        f.write("# Netscape HTTP Cookie File\n")
        f.write("# This file is generated by browser_cookie3\n\n")
        for cookie in cookies:
            f.write(
                f"{cookie.domain}\t"
                f"{'TRUE' if cookie.domain.startswith('.') else 'FALSE'}\t"
                f"{cookie.path}\t"
                f"{'TRUE' if cookie.secure else 'FALSE'}\t"
                f"{int(cookie.expires) if cookie.expires else 0}\t"
                f"{cookie.name}\t"
                f"{cookie.value}\n"
            )
    return temp_cookiefile.name

def search_videos(query):
    try:
        # YouTube'da arama yap
        cookiefile = get_cookiefile()
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,  # Video detaylarını indirmeden listele
            'cookiefile': cookiefile  # Çerez dosyasını belirt
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_results = ydl.extract_info(f"ytsearch10:{query}", download=False)

        # Sonuçları işleme
        videos = [
            {
                'id': entry['id'],
                'title': entry['title'],
                'url': f"https://www.youtube.com/watch?v={entry['id']}"
            }
            for entry in search_results.get('entries', [])
        ]

        return render_template('search_results.html', videos=videos)

    except Exception as e:
        return f"Error: {str(e)}", 500

def download_video(video_url):
    try:
        # MP3 için yt-dlp ayarları
        cookiefile = get_cookiefile()
        output_dir = tempfile.mkdtemp()  # Geçici bir klasör oluştur
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'cookiefile': cookiefile,  # Çerez dosyasını belirt
            'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),  # Geçici klasöre kaydet
        }

        # Video bilgilerini al ve indir
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(video_url, download=True)
            video_title = result.get('title', 'audio')
            downloaded_file = ydl.prepare_filename(result).replace('.webm', '.mp3').replace('.m4a', '.mp3')

        # Güvenli dosya adı oluştur
        sanitized_title = re.sub(r'[^\w\s-]', '', unicodedata.normalize('NFKD', video_title)).strip().replace(' ', '_')
        encoded_filename = quote(f"{sanitized_title}.mp3")  # Unicode karakterleri encode et

        # Dosyayı sun
        def generate():
            with open(downloaded_file, 'rb') as f:
                while chunk := f.read(64 * 1024):  # Chunked reading
                    yield chunk

        return Response(
            generate(),
            content_type='audio/mpeg',
            headers={
                'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}",
                'Cache-Control': 'no-cache',
                'Transfer-Encoding': 'chunked',
            },
        )

    except Exception as e:
        return f"Error: {str(e)}", 500

    finally:
        # Geçici dosyaları temizle
        if os.path.exists(output_dir):
            for file in os.listdir(output_dir):
                os.remove(os.path.join(output_dir, file))
            os.rmdir(output_dir)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port='5000', debug=True, threaded=True)
