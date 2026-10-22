"""Run locally in a terminal. Passwords are never accepted on the command line."""
from pathlib import Path
import sys,getpass
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.auth import bootstrap_admin,has_admin

def main():
    if has_admin():raise SystemExit('An active administrator already exists. No changes made.')
    name=input('Administrator username [admin_123]: ').strip() or 'admin_123'
    password=getpass.getpass('New administrator password (15–128 characters): ')
    confirm=getpass.getpass('Confirm password: ')
    if password!=confirm:raise SystemExit('Passwords do not match. No account created.')
    try:bootstrap_admin(name,password)
    except ValueError as exc:raise SystemExit(str(exc))
    print('Administrator created. Start the app and sign in. No password was printed or saved as plaintext.')
if __name__=='__main__':main()
