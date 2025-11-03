# LinkedIn Agent

This project automates the process of opening a specific LinkedIn connections page, searching for a particular person's name across multiple pages, scraping their profile for specified information, performing a Google search based on the scraped data, and outputting the specified information.

## Project Structure

```
linkedin-agent
├── src
│   ├── basic_agent.py          # Initializes the agent and sets up the environment
│   ├── agent.py                # Main class for the agent, orchestrating tasks
│   ├── scrapers
│   │   ├── linkedin_scraper.py  # Handles LinkedIn profile scraping
│   │   └── google_search.py      # Performs Google searches based on scraped data
│   ├── services
│   │   └── browser_service.py    # Manages browser automation tasks
│   ├── models
│   │   └── profile.py            # Data model for storing scraped profile information
│   ├── tools
│   │   └── linkedin_tools.py      # Utility functions for LinkedIn tasks
│   └── utils
│       └── parsers.py            # Functions for parsing and formatting scraped data
├── tests
│   └── test_linkedin_scraper.py  # Unit tests for the LinkedIn scraper
├── .env.example                  # Template for environment variables
├── .gitignore                    # Specifies files to ignore in version control
├── requirements.txt              # Lists project dependencies
├── pyproject.toml                # Project configuration
└── README.md                     # Documentation for the project
```

## Setup Instructions

1. Clone the repository:
   ```
   git clone <repository-url>
   cd linkedin-agent
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Configure environment variables by copying `.env.example` to `.env` and filling in the necessary values.

## Usage Guidelines

To run the agent, execute the following command:
```
python src/basic_agent.py
```

## Overview of Functionality

- The agent opens a specified LinkedIn connections page.
- It searches for a particular person's name across multiple pages.
- The agent scrapes the profile for specified information.
- It performs a Google search based on the scraped data.
- Finally, it outputs the specified information in a structured format.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.# Beta_Tracker
