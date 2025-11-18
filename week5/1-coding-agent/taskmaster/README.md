# Running the Django App

This project uses [uv](https://github.com/astral-sh/uv) for Python environment and dependency management, and Django as the web framework.

## Prerequisites

- Python 3.8+
- [uv](https://github.com/astral-sh/uv) installed globally (`pip install uv`)

## Setup and Running

1. **Install dependencies**:
   ```sh
   make install
   ```

2. **Apply database migrations:**
   ```sh
   make migrate
   ```

3. **Run the development server:**
   ```sh
   make run
   ```

4. Open your browser and go to [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

## Management Commands

- Send deadline reminder emails (uses console email backend in development):

```sh
python manage.py send_deadline_reminders
```
