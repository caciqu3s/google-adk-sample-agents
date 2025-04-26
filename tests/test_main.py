"""
Test module for main application.
"""

from src.main import main

def test_main(capsys):
    """Test the main function."""
    main()
    captured = capsys.readouterr()
    assert "Application started!" in captured.out 