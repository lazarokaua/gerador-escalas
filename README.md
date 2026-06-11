# Weekly Conveyor Scale Generator (Gerador de Escala de Esteiras)

A dynamic and automated weekly scale rotation manager built with Streamlit and Pandas. It handles team rotation logic, weekly support roles (`APOIO`), sector capacity limits, and provides options to download generated schedules as Excel spreadsheets or print them directly.

## Features

- **Dynamic Scale Generation**: Generates rotation schedules automatically based on the ISO week number.
- **Team Management**: Add or remove team members directly from the UI, updating the configuration in real-time.
- **Sector Customization**: Create new work sectors, set staff capacity requirements per sector, and manage them.
- **Exporting Options**: 
  - Save directly to your local `Downloads` directory as an Excel spreadsheet.
  - Download in-memory spreadsheet via the browser.
  - High-resolution print styling for clean printing layout or PDF export.

## File Structure

- `app.py`: Main Streamlit UI dashboard.
- `escala_engine.py`: Core logic for managing rotations, reading/writing configuration, and exporting data.
- `escala_config.json`: Persistent storage for team names and sector configurations.
- `requirements.txt`: Python package dependencies.
- `.gitignore`: Standard Git exclusions for local builds, environment folders, and generated Excel spreadsheets.

## Getting Started

### Prerequisites

Make sure you have Python 3.8+ installed.

### Installation

1. Clone or copy this directory to your environment.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Running Locally

To launch the Streamlit application, run the following command in your terminal:
```bash
streamlit run app.py
```
This will start the local server and open the app in your default web browser (typically at `http://localhost:8501`).

## Deployment

This repository is ready to be published to a public GitHub repository and deployed directly on **Streamlit Cloud**:

1. Push this folder to a new public GitHub repository.
2. Go to [share.streamlit.io](https://share.streamlit.io/) and log in with your GitHub account.
3. Click **New app**, select your repository, branch, and set the main file path to `app.py`.
4. Click **Deploy!**
