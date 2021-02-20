#!/usr/bin/env python

import argparse
import functools
import os.path
import pathlib
import subprocess
import tempfile
import venv

import pygal


parser = argparse.ArgumentParser(
    prog='weasyperf', description='Test WeasyPrint performance.')
parser.add_argument('-s', '--sample', action='append', help='HTML samples.')
parser.add_argument(
    '-v', '--version', action='append', help='WeasyPrint versions.')

args = parser.parse_args()

print('* Generating virtual environment')

temp = pathlib.Path(tempfile.gettempdir()) / 'weasyperf'
pip = temp / 'bin' / 'pip'
python = temp / 'bin' / 'python'
current = pathlib.Path(__file__).parent

samples = args.sample or sorted(
    (path.name for path in (current / 'samples').iterdir()))
versions = args.version or sorted(
    (path.name for path in (current / 'versions').iterdir()), reverse=True)

run = functools.partial(subprocess.run, capture_output=True)

venv.create(temp, with_pip=True)
run((pip, 'install', '--upgrade', 'pip'))
run((pip, 'install', '--upgrade', 'setuptools'))
run((pip, 'install', 'memory_profiler'))

for sample in samples:
    path = current / 'samples' / sample

    config = pygal.Config()
    config.title = f'Time and memory for "{sample}"'
    config.x_title = 'Time (seconds)'
    config.y_title = 'Memory (megabytes)'
    config.dots_size = 0.5
    config.show_x_guides = True
    xy_graph = pygal.XY(config)
    config = pygal.Config()
    config.title = f'Memory for "{sample}"'
    config.x_title = 'Memory (megabytes)'
    mem_graph = pygal.HorizontalBar(config)
    config = pygal.Config()
    config.title = f'Time for "{sample}"'
    config.x_title = 'Time (seconds)'
    time_graph = pygal.HorizontalBar(config)
    config = pygal.Config()
    config.title = f'PDF size for "{sample}"'
    config.x_title = 'Size (kilobytes)'
    size_graph = pygal.HorizontalBar(config)

    for data_file in path.glob('*.dat'):
        data_file.unlink()

    for version in versions:
        if sample == 'json' and version < '43':
            # This sample is broken with older versions
            continue

        print(f'* Installing WeasyPrint {version}')
        if version.startswith('file://'):
            run((pip, 'install', '--force', version[7:]))
            version = 'file'
        else:
            requirements = current / 'versions' / version
            if requirements.exists():
                print('  (using fixed requirements)')
                run((pip, 'install', '--force', '-r', requirements))
            else:
                run((pip, 'install', '--force', f'weasyprint=={version}'))

        print(f'* Rendering {sample} with WeasyPrint {version}')
        run((
            python, '-m', 'mprof', 'run', '-o', path / f'mprof-{version}.dat',
            python, '-m', 'weasyprint',
            path / f'{sample}.html', path / f'{sample}-{version}.pdf',
        ))

        lines = [
            line.split() for line in
            (path / f'mprof-{version}.dat').read_text().split('\n') if line]
        timestamp = float(lines[1][2])

        xy_graph.add(f'{version}', [
            [float(line[2]) - timestamp, float(line[1])]
            for line in lines if line[0] == 'MEM'])
        mem_graph.add(f'{version}', max(
            float(line[1]) for line in lines if line[0] == 'MEM'))
        time_graph.add(f'{version}', float(lines[-1][2]) - timestamp)
        size_graph.add(
            f'{version}',
            os.path.getsize(path / f'{sample}-{version}.pdf') / 1000)

    (path / 'xy_graph.svg').write_bytes(xy_graph.render())
    (path / 'mem_graph.svg').write_bytes(mem_graph.render())
    (path / 'time_graph.svg').write_bytes(time_graph.render())
    (path / 'size_graph.svg').write_bytes(size_graph.render())
