# 🚀 Free 4K YouTube Video & Audio Downloader

A simple, powerful, and self-hostable web application to download YouTube videos in the highest possible quality (up to 8K) and extract high-fidelity MP3 audio. Built with **Python, Flask, and yt-dlp**.

✨ **Live Demo:** [yt.ankitsoni.in](https://yt.ankitsoni.in)  
_(Note: Replace this with a screenshot of your application.)_

---

## 📋 Table of Contents

- [About The Project](#-about-the-project)
- [Key Features](#-key-features)
- [Tech Stack](#-tech-stack)
- [Getting Started: Deployment Guide](#-getting-started-deployment-guide)
  - [Prerequisites](#prerequisites)
  - [Deployment with Dokploy](#deployment-with-dokploy)
- [Contributing](#-contributing)
- [License](#-license)
- [Contact & Support](#-contact--support)

---

## 📖 About The Project

This project provides a clean, user-friendly web interface for downloading YouTube content.  
It was built as a **fast, free, and reliable alternative** to ad-heavy downloader websites.

The application is containerized with **Docker**, making it incredibly easy to deploy on any server that supports Docker—especially with platforms like **Dokploy**.

- The **backend** uses `yt-dlp` to handle downloading logic, known for its reliability and extensive features.
- The **frontend** streams download progress in real-time, providing a smooth user experience.

---

## ✨ Key Features

- **Highest Quality Downloads**: Fetches the best available quality (HD, 4K, 8K).
- **MP3 Audio Extraction**: Convert any video to high-quality MP3.
- **Real-Time Progress**: Live progress bar with exact download status.
- **Video Info Fetching**: Thumbnail, title, and details displayed before downloading.
- **SEO-Optimized**: Content-rich, SEO-friendly landing page.
- **Containerized & Portable**: Easy deployment with Docker and Dokploy.
- **100% Free & Open Source**: No ads, no tracking, no limitations.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.11+ with Flask
- **Video Processing**: yt-dlp & ffmpeg
- **Frontend**: HTML5, Tailwind CSS, JavaScript
- **Web Server**: Gunicorn (production)
- **Containerization**: Docker & Docker Compose
- **Deployment**: Dokploy

---

## 🚀 Getting Started: Deployment Guide

### Prerequisites

- A server (e.g., Ubuntu) with **Docker** and **Dokploy** installed
- A registered domain name (e.g., `yt.ankitsoni.in`)

---

### Deployment with Dokploy (Recommended)

#### 1. Fork this Repository

Fork this GitHub repository to your own account.

#### 2. Create a New App in Dokploy

- Log in to your Dokploy dashboard
- Click to create a new **App**
- Select **GitHub** as the provider and connect your account

#### 3. Configure the Deployment

- Choose the forked repository
- Dokploy will detect the `Dockerfile` and configure build settings automatically
- **Port Mapping**: App runs on port **8000**
- **Volumes**: The `docker-compose.yml` defines a volume for `/app/downloads` to persist downloaded files

#### 4. Deploy

Click **Deploy**. Dokploy will pull the code, build the image, and start the app.

#### 5. Assign a Domain

- In Dokploy, go to the **Domains** tab
- Enter your domain (`yt.ankitsoni.in`)
- SSL (HTTPS) will be configured automatically

✅ Your application is now live!

---

## 🤝 Contributing

Contributions are welcome! To contribute:

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

Distributed under the **MIT License**.  
See the [LICENSE](LICENSE) file for details.

---

## 📧 Contact & Support

- **Author**: Ankit Soni
- **Email**: [hello@ankitsoni.in](mailto:hello@ankitsoni.in)
- **Project Link**: [GitHub Repository](https://github.com/ankitsoniblogger/yt-downloader) _(replace with your actual repo link)_

---
