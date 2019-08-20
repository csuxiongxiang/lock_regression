import paramiko
import time

def RegionSplit():
        ssh = paramiko.SSHClient()
        key = paramiko.AutoAddPolicy()
        ssh.set_missing_host_key_policy(key)
        ssh.connect('10.10.23.35', 22, 'root', 'lock12#$')
        stdin, stdout, stderr = ssh.exec_command('hbase shell /opt/lockRegression/regionsplit.sql')
        print("")
        print("hbase shell:")
        print("hbase(main):001:0> split 'TRAFODION.S_LOCKREGRESSION.EMP_SPLIT','e'")
        for i in stdout.readlines():
            print(i)

        time.sleep(5)

if __name__ == '__main__':
    RegionSplit()