from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

setup(
    name="agri_coldchain",
    version="0.0.1",
    description="Agri-Processing / Cold Chain MSME Traceability for ERPNext v15",
    author="Your Organisation",
    author_email="info@example.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
