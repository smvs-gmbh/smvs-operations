"""Import the prepared snapshot into the verified EMPTY Operations schema only."""

import hashlib
import json
import shlex
import subprocess
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
REMOTE = r"""
import json,sys,tempfile,subprocess,hashlib,gzip,shutil,re
from pathlib import Path
x=json.load(sys.stdin)
source=Path('/home/jelastic/smvs-operations-import-20261109/smvs_operations.sql.gz')
digest=hashlib.sha256()
with source.open('rb') as stream:
 for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
assert digest.hexdigest()==x['sha256'],'Transfer checksum mismatch; import refused'
assert all(re.fullmatch(r'[A-Za-z0-9_]+', name) for name in x['counts'])
def option(v):return '"'+v.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n').replace('\r','\\r')+'"'
with tempfile.TemporaryDirectory(prefix='smvs-db-admin-') as directory:
 config=Path(directory)/'client.cnf'
 config.write_text('[client]\nuser='+option(x['user'])+'\npassword='+option(x['password'])+'\nprotocol=SOCKET\nsocket=/var/lib/mysql/mysql.sock\n')
 config.chmod(0o600)
 args=['mysql','--defaults-extra-file='+str(config),'--batch','--skip-column-names','--default-character-set=utf8mb4','--max-allowed-packet=1G']
 def query(sql):
  result=subprocess.run(args,input=sql,capture_output=True,text=True)
  if result.returncode:raise RuntimeError('SQL verification failed; credentials/data suppressed')
  return result.stdout.strip()
 assert query("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='smvs_operations';")=='0','Target is not empty; import refused'
 log=source.parent/'import-errors.log'
 with log.open('wb') as errors:
  log.chmod(0o600)
  process=subprocess.Popen(args+['smvs_operations'],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=errors)
  try:
   with gzip.open(source,'rb') as stream:shutil.copyfileobj(stream,process.stdin,1024*1024)
  except BrokenPipeError:pass
  process.stdin.close()
  status=process.wait()
 if status:
  print('Snapshot import failed; protected error log retained on database node.');sys.exit(1)
 tables=query('SHOW TABLES FROM smvs_operations;').splitlines()
 assert set(tables)==set(x['counts']),'Table set mismatch'
 mismatch={}
 for table in tables:
  count=int(query('SELECT COUNT(*) FROM smvs_operations.`'+table+'`;'))
  if count!=x['counts'][table]:mismatch[table]=[x['counts'][table],count]
 print('Imported tables:',len(tables))
 print('Row-count differences:',json.dumps(mismatch))
 print('Schema version:',query('SELECT version_num FROM smvs_operations.alembic_version;'))
 bad=query('SELECT COUNT(*) FROM smvs_operations.artifact_contents WHERE sha256 <> SHA2(artifact_bytes,256);')
 print('Artifact checksum failures:',bad)
 assert not mismatch and bad=='0','Imported data validation failed'
 source.unlink()
 if log.stat().st_size==0:log.unlink()
 print('Snapshot validated; temporary remote dump removed.')
"""


def main():
    config = dotenv_values(ROOT / ".env.mysql-bootstrap")
    work = ROOT / "tmp/jelastic-operations-migration"
    assert config.get("MYSQL_ADMIN_PASSWORD"), "Admin password missing"
    with (work / "smvs_operations.sql.gz").open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    payload = {
        "user": config["MYSQL_ADMIN_USER"],
        "password": config["MYSQL_ADMIN_PASSWORD"],
        "sha256": digest,
        "counts": json.loads((work / "source-counts.json").read_text()),
    }
    command = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        "ConnectTimeout=8",
        "-p",
        "3022",
        "220544-9004@gate.jpc.infomaniak.com",
        "python3 -c " + shlex.quote(REMOTE),
    ]
    result = subprocess.run(
        command, input=json.dumps(payload), capture_output=True, text=True, check=False
    )
    print(result.stdout, end="")
    if result.returncode:
        print(
            "Migration failed; no other schema was targeted. Inspect the protected remote error log."
        )
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
