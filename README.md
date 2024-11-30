# Movie Recommendation and Discussion System

## Overview
This project is a **Movie Recommendation and Discussion System** that combines a Netflix-style interface for browsing movies with a discussion forum for users to interact and share their opinions. The system includes functionalities for user authentication, creating and viewing discussion threads, and dynamic display of movie posters.

---

## Features

### User Authentication
- **Login** and **Register** functionality with user profile information.
- Support for profile pictures and user-specific dashboards.

### Netflix-Style Movie Browsing
- Movie posters displayed in horizontal swipeable rows categorized into sections (e.g., Trending, Top Rated, New Releases).
- Interactive poster enlargements on hover.
- Left and right scroll buttons for easy navigation through rows.

### Discussion Threads
- Display of discussion threads as square boxes with titles and content snippets.
- Logged-in users can:
  - Create new threads.
  - View, edit, or delete their own threads.
  - Reply to existing threads.
- Non-logged-in users can only view threads and their content.

### Database Integration
- MySQL is used for managing user data, threads, and movie information.
- The `DB init.txt` file contains all necessary SQL schemas for initializing the database.

### Responsive Design
- Fully responsive layout optimized for desktop and mobile screens.
- Dynamic grid layout for threads and adaptive poster sizes.

---

## Installation

### Prerequisites
- Python 3.8 or higher
- MySQL server
- Required Python packages (listed in `requirements.txt`)

### Step 1: Clone the Repository
```bash
git clone https://github.com/yourusername/movie-recommendation-discussion.git
cd movie-recommendation-discussion
Step 2: Install Dependencies

Create and activate a virtual environment (optional but recommended):

python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`

Install the required packages:

pip install -r requirements.txt

Step 3: Initialize the Database

    Open the DB init.txt file.

    Execute the SQL commands in your MySQL server to set up the database schema.

    Update the config.py file in the project directory with your MySQL credentials:

    MYSQL_HOST = 'localhost'
    MYSQL_USER = 'your_username'
    MYSQL_PASSWORD = 'your_password'
    MYSQL_DB = 'your_database_name'

Step 4: Run the Application

Start the Flask server:

python app.py

Access the application in your browser at http://127.0.0.1:5000/.
Usage
Home Page

    Displays movie posters in a Netflix-style layout.
    Use navigation buttons to browse through movies.

Discussions

    View discussion threads as square boxes with titles and snippets.
    Logged-in users can create new threads and reply to existing ones.
    Threads include metadata such as the creator's name and timestamps.

Authentication

    Register a new account with basic information (name, email, password, gender, and optional profile picture).
    Log in to access personalized features such as thread creation and replies.

File Structure

project-directory/
├── app.py              # Main Flask application
├── config.py           # Configuration file for database credentials
├── templates/          # HTML templates
│   ├── base.html       # Base layout
│   ├── home.html       # Netflix-style movie browsing page
│   ├── discussions.html# Discussions page
│   ├── create_thread.html  # Page for creating new threads
│   └── ...             # Other templates
├── static/             # Static files (CSS, JS, images)
│   ├── styles.css      # Stylesheet (if used)
│   └── ...             # Other static files
├── DB init.txt         # MySQL database initialization script
├── requirements.txt    # Required Python packages
└── README.md           # Project documentation

Technologies Used
Backend

    Flask: Web framework for Python.
    MySQL: Database for managing user and thread data.

Frontend

    HTML/CSS: For layout and styling.
    JavaScript: For interactive elements like scrollable movie rows.

Other Tools

    Flask-Login: For user session management.
    Responsive Design: Mobile-friendly layout using CSS.

Future Enhancements

    Movie Recommendation Engine: Implement recommendation algorithms based on user preferences.
    Real Movie Data: Integrate with a movie API (e.g., TMDb) to fetch real movie details and posters.
    Search and Filters: Add search functionality and advanced filters for discussions and movies.
    User Notifications: Notify users of replies to their threads or updates in discussions.

License

This project is licensed under the MIT License.
Acknowledgments

    Placeholder movie images were sourced from Placeholder.com.
    Inspired by the Netflix UI for movie browsing.