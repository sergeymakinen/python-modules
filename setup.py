from setuptools import setup

setup(name='sergeymakinen',
      version='1.1.0b3',
      description='Sergey Makinen Python modules',
      license='MIT',
      author='Sergey Makinen',
      author_email='sergey@makinen.ru',
      url='https://github.com/sergeymakinen/python-modules',
      packages=['sergeymakinen'],
      classifiers=[
            'Development Status :: 4 - Beta',
            'Intended Audience :: Developers',
            'Topic :: Software Development :: Libraries',
            'License :: OSI Approved :: MIT License',
            'Programming Language :: Python :: 3',
            'Programming Language :: Python :: 3.2',
      ],
      keywords='sergeymakinen library development',
      install_requires=['python-dateutil>=2.3'])
