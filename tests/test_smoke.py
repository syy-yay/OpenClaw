import subprocess, time, urllib.request, pytest

STAGING_PORT = 18080
CONTAINER_NAME = "staging-test"

def get_tag():
    r = subprocess.run(["git", "-C", "/home/user/openclaw-project", "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip()

@pytest.fixture(scope="session", autouse=True)
def staging():
    tag = get_tag()
    subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True)
    # 容器内 Flask 运行在 port 5001，映射到宿主机 port 18080
    subprocess.run(["docker", "run", "-d", "--name", CONTAINER_NAME, "-p", f"{STAGING_PORT}:5001", f"192.168.1.200:5000/openclaw/myapp:{tag}"], check=True)
    time.sleep(3)
    yield
    subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True)

def test_service_up():
    resp = urllib.request.urlopen(f"http://localhost:{STAGING_PORT}", timeout=5)
    assert resp.status == 200

def test_response_not_empty():
    resp = urllib.request.urlopen(f"http://localhost:{STAGING_PORT}", timeout=5)
    assert len(resp.read()) > 0
