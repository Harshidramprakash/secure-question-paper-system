"""Application entry point — run the Flask development server."""
from app import create_app

app = create_app()

if __name__ == '__main__':
    print('\n' + '=' * 60)
    print('  Secure Question Paper Assembly System (SQPAS)')
    print('  Running on: http://127.0.0.1:5000')
    print('  Press Ctrl+C to stop')
    print('=' * 60 + '\n')
    app.run(host='127.0.0.1', port=5000, debug=True)
