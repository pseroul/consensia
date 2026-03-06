# Testing Guide for Brainiac5 Backend

This document provides an overview of the testing setup and best practices for testing the Brainiac5 backend application.

## Testing Framework

The backend uses **pytest** as the testing framework, combined with **unittest.mock** for mocking dependencies and **TestClient** for API testing.

### Key Features

- **pytest**: Powerful testing framework with rich plugin ecosystem
- **unittest.mock**: Built-in mocking library for Python
- **FastAPI TestClient**: For testing API endpoints
- **Coverage.py**: Code coverage reporting with 80% threshold
- **SQLite**: Temporary databases for isolated testing

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run tests with verbose output
pytest -v

# Run tests with coverage report
pytest --cov=backend

# Run tests with coverage and HTML report
pytest --cov=backend --cov-report=html

# Run specific test file
pytest backend/tests/test_main.py

# Run specific test class
pytest backend/tests/test_main.py::TestMainAPI

# Run specific test method
pytest backend/tests/test_main.py::TestMainAPI::test_health_check

# Run tests in watch mode (requires pytest-watch)
pytest-watch

# Run tests with detailed traceback
pytest --tb=short
```

### Test Commands

- `pytest` - Run all tests
- `pytest -v` - Run with verbose output
- `pytest --cov=backend` - Run with coverage
- `pytest --cov=backend --cov-report=html` - Generate HTML coverage report
- `pytest backend/tests/test_main.py` - Run specific test file

## Test Structure

Tests are organized in the `backend/tests/` directory:

```
backend/
├── tests/
│   ├── test_chroma_client.py
│   ├── test_data_handler.py
│   ├── test_data_similarity.py
│   ├── test_main.py
│   ├── test_authenticator.py
│   ├── test_utils.py
│   └── run_tests.py
├── main.py
├── authenticator.py
├── chroma_client.py
├── data_handler.py
├── data_similarity.py
├── utils.py
└── ...
```

Each test file follows the same pattern:
- **Test classes** for different components/modules
- **setup_method** for test setup
- **teardown_method** for cleanup
- **Test methods** with descriptive names

## Writing Tests

### Basic Test Example

```python
import pytest
from unittest.mock import patch
from backend.utils import format_text

def test_format_text():
    """Test format_text function"""
    result = format_text("Test Idea", "This is a test", ["tag1"])
    expected = "Test Idea / [tag1] : This is a test"
    assert result == expected
```

### Common Testing Patterns

#### 1. Unit Tests
```python
def test_add_numbers():
    """Test simple function"""
    result = add(2, 3)
    assert result == 5
```

#### 2. Mocking Dependencies
```python
@patch('backend.data_handler.get_ideas')
def test_get_all_ideas(mock_get_ideas):
    """Test getting all ideas with mocked database"""
    # Setup mock
    mock_get_ideas.return_value = [
        {"id": 1, "title": "Test Idea", "content": "Content"}
    ]
    
    # Call function
    result = get_all_ideas()
    
    # Assert
    assert len(result) == 1
    assert result[0]["title"] == "Test Idea"
```

#### 3. API Tests with TestClient
```python
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
```

#### 4. Database Tests
```python
import sqlite3
from backend.data_handler import init_database, get_ideas

def test_get_ideas_empty():
    """Test get_ideas when database is empty"""
    # Setup temporary database
    test_db = ":memory:"
    
    # Initialize database
    init_database(test_db)
    
    # Test
    result = get_ideas(test_db)
    assert isinstance(result, list)
    assert len(result) == 0
```

#### 5. Error Handling Tests
```python
@patch('backend.data_handler.get_ideas')
def test_error_handling(mock_get_ideas):
    """Test error handling in API endpoint"""
    # Setup mock to raise exception
    mock_get_ideas.side_effect = Exception("Database error")
    
    # Call endpoint
    response = client.get("/ideas")
    
    # Assert error response
    assert response.status_code == 500
    assert "Error retrieving data" in response.json()["detail"]
```

## Test Setup

### Test Fixtures

The test files use pytest fixtures and setup/teardown methods:

```python
class TestDataHandler:
    """Test cases for data_handler functions"""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Create temporary database
        self.test_db = os.path.join(os.path.dirname(__file__), "test_database.db")
        os.environ["NAME_DB"] = self.test_db
        
        # Initialize database
        init_database()
        
        # Insert test user
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                      ("testuser", "test@example.com", "password"))
        conn.commit()
        conn.close()

    def teardown_method(self):
        """Clean up after each test method."""
        # Remove test database
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
```

### Mocking Strategies

1. **Mock External Services**: Use `@patch` decorator to mock external dependencies
2. **Mock Database Operations**: Use in-memory databases or mock database functions
3. **Mock API Calls**: Use `unittest.mock` to mock HTTP requests
4. **Mock Time**: Use `freeze_time` from `freezegun` for time-dependent tests

## Best Practices

### 1. Test Structure
- Use **descriptive class names** (e.g., `TestDataHandler`, `TestMainAPI`)
- Use **descriptive method names** (e.g., `test_get_ideas_empty`, `test_create_idea_success`)
- Keep **one test per behavior** - don't test multiple things in one test
- Use **setup/teardown** for test isolation

### 2. Naming Conventions
- Test files: `test_<module>.py` (e.g., `test_data_handler.py`)
- Test classes: `Test<Component>` (e.g., `TestDataHandler`)
- Test methods: `test_<behavior>` (e.g., `test_create_idea_success`)
- Use **clear, descriptive names** that explain what's being tested

### 3. Assertions
- Use **specific assertions** (not just `assert True`)
- Use **pytest assertions** for better error messages
- Test **both happy paths and edge cases**
- Test **error conditions and exceptions**

### 4. Mocking
- **Mock external dependencies** (databases, APIs, file systems)
- **Keep mocks minimal** - only mock what's necessary
- **Verify mock calls** - check that functions were called with correct parameters
- **Use real code** for simple, fast operations

### 5. Database Testing
- Use **temporary databases** for isolation
- Use **in-memory SQLite** for fast tests
- **Clean up** after each test
- **Test both success and failure** scenarios

### 6. API Testing
- Test **all HTTP methods** (GET, POST, PUT, DELETE)
- Test **success responses** (200, 201)
- Test **error responses** (400, 401, 404, 500)
- Test **input validation**
- Test **authentication/authorization**

## Coverage

The project has a **80% coverage threshold** for:
- Lines
- Functions  
- Branches
- Statements

To check coverage:

```bash
# Basic coverage
pytest --cov=backend

# HTML coverage report
pytest --cov=backend --cov-report=html

# View HTML report in browser
open htmlcov/index.html  # macOS
start htmlcov\index.html  # Windows
```

### Coverage Reports

- **Terminal output**: Shows coverage percentages
- **HTML report**: Interactive coverage report with clickable code
- **JSON report**: Machine-readable coverage data
- **XML report**: For CI/CD integration

## Debugging Tests

### Common Issues

1. **Test not running**: Check file name starts with `test_`
2. **Test failing**: Use `-v` flag for verbose output
3. **Assertion error**: Check expected vs actual values
4. **Import error**: Ensure proper module paths
5. **Mock not working**: Verify mock location and target

### Debugging Tools

```python
# Print debug information
def test_debug():
    print("Debug: value =", value)
    
# Use pytest's -s flag to see print output
pytest -s

# Use breakpoint() for interactive debugging
def test_interactive():
    breakpoint()  # Starts Python debugger
    
# Use assert with custom messages
assert result == expected, f"Expected {expected}, got {result}"
```

### Common pytest Options

```bash
# Verbose output
pytest -v

# Show local variables on failure
pytest --pdb

# Stop after first failure
pytest -x

# Fail on warnings
pytest -W error

# Show duration of each test
pytest --durations=10

# Run tests by keyword
pytest -k "test_health"

# Run tests by marker
pytest -m "slow"
```

## CI/CD Integration

Tests are configured to run in CI environments with:
- **Coverage reporting** - Ensures code quality
- **Strict failure** - Fails build on test failures
- **Clean environment** - Isolated test runs
- **Parallel execution** - Faster test runs

### Example CI Configuration (GitHub Actions)

```yaml
name: Python Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.10'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r backend/requirements.txt
        pip install pytest pytest-cov
    
    - name: Run tests with coverage
      run: |
        cd backend
        pytest --cov=backend --cov-report=xml
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v1
      with:
        file: ./backend/coverage.xml
```

## Contributing

When adding new features or fixing bugs:
1. **Write tests first** - Test-driven development
2. **Test new functionality** - Ensure all behaviors are tested
3. **Test edge cases** - Consider error conditions
4. **Maintain coverage** - Don't let coverage drop below 80%
5. **Run tests locally** - Before submitting PRs
6. **Fix failing tests** - Don't ignore test failures

## Test Organization

### By Module
- `test_chroma_client.py` - ChromaDB client tests
- `test_data_handler.py` - Database operations tests
- `test_data_similarity.py` - Data similarity algorithms tests
- `test_main.py` - API endpoint tests
- `test_authenticator.py` - Authentication tests
- `test_utils.py` - Utility function tests

### By Type
- **Unit tests** - Test individual functions
- **Integration tests** - Test component interactions
- **API tests** - Test HTTP endpoints
- **Database tests** - Test SQLite operations
- **Error tests** - Test error handling

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [unittest.mock Documentation](https://docs.python.org/3/library/unittest.mock.html)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [SQLite Documentation](https://www.sqlite.org/docs.html)

## Tips and Tricks

### Speed Up Tests
```bash
# Use xdist for parallel test execution
pip install pytest-xdist
pytest -n 4  # Run tests in 4 processes

# Cache test results
pip install pytest-cache
```

### Organize Large Test Files
```python
# Use pytest markers to categorize tests
import pytest

@pytest.mark.slow
def test_slow_operation():
    ...

@pytest.mark.integration
def test_api_integration():
    ...

# Run specific marker
pytest -m "slow"
```

### Parametrize Tests
```python
import pytest

@pytest.mark.parametrize("input,expected", [
    ("hello", "HELLO"),
    ("world", "WORLD"),
    ("test", "TEST"),
])
def test_uppercase(input, expected):
    assert uppercase(input) == expected
```

### Temporary Test Skipping
```python
import pytest

@pytest.mark.skip(reason="Feature not implemented yet")
def test_new_feature():
    ...

@pytest.mark.xfail(reason="Known issue")
def test_flaky_test():
    ...
```

This comprehensive testing guide provides everything needed to write, run, and maintain high-quality tests for the Brainiac5 backend application.
