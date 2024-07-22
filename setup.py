# -*- coding:utf-8 -*-
##############################################################
# Created Date: Wednesday, July 12th 2023
# Contact Info: luoxiangyong01@gmail.com
# Author/Copyright: Mr. Xiangyong Luo
##############################################################


import gtfs2gmns as gg
import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

try:
    # if have requirements.txt file inside the folder
    with open("requirements.txt", "r", encoding="utf-8") as f:
        modules_needed = [i.strip() for i in f.readlines()]
except Exception:
    modules_needed = []

setuptools.setup(
    name=gg.pkg_name,  # Replace with your own username
    version=gg.pkg_version,
    author=gg.pkg_author,
    author_email=gg.pkg_email,

    keywords=["GTFS", "GMNS", "Public Transportation", "Equity"],
    description="A class-based instance designed for reading, converting, analyzing, and visualizing GTFS data",

    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/xyluo25/gtfs2gmns",

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        'Operating System :: OS Independent',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: Implementation',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Topic :: Software Development :: Libraries'
    ],
    python_requires='>=3.10',
    install_requires=modules_needed,

    packages=setuptools.find_packages(),
    include_package_data=True,
    # package_dir={'': 'pyufunc'},
    package_data={'': ["*.json", "*.txt"],
                  },
    project_urls={
        'Homepage': 'https://github.com/xyluo25/gtfs2gmns',
        # 'Documentation': 'https://github.com/xyluo25/pyufunc',
        'Bug Tracker': 'https://github.com/xyluo25/gtfs2gmns/issues',
        # 'Source Code': '',
        # 'Download': '',
        # 'Publication': '',
        # 'Citation': '',
        'License': 'https://github.com/xyluo25/gtfs2gmns/blob/main/LICENSE',
        # 'Acknowledgement': '',
        # 'FAQs': '',
        'Contact': 'https://github.com/xyluo25',
    },
    platforms=["all"],
    license='MIT License',
)
