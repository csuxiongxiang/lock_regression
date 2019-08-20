import paramiko
import time

def lockManage():
        ssh = paramiko.SSHClient()
        key = paramiko.AutoAddPolicy()
        ssh.set_missing_host_key_policy(key)
        ssh.connect('10.10.23.23', 22, 'root', 'lock12#$')
        str = """cd /opt/lockRegression/lockManager/ && ./run.sh -h 10.10.23.23"""
        stdin, stdout, stderr = ssh.exec_command(str)
        print("")
        print("======================================== lock infomation ========================================")
        for i in stderr.readlines():
            print(i)

        for i in stdout.readlines():
            print(i)

        time.sleep(5)

if __name__ == '__main__':
    lockManage()