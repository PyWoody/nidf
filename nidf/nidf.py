#! /usr/bin/env python3

import curio
import hashlib
import os
import re
import zipfile


__all__ = ['Nidf', 'generate_hash', 'search_zipfile']


class Nidf:

    def __init__(self, callback=None):
        if callback is None:
            callback = async_print
        self.callback = callback
        self.items_queue = curio.Queue()
        self.paths_queue = curio.Queue()
        self.zip_paths_queue = curio.Queue()
        self.check_hash = False
        self.check_zips = False
        self.ignore_errors = False
        self.name_re = None
        self._type = None
        self.master_hash = None
        self.__cancelled = False

    async def __call__(
                self,
                root,
                *,
                name=None,
                _type=None,
                _hash=False,
                check_zips=False,
                ignore_errors=False,
            ):
        """
        An asyncrounus search file and/or directory search.

        Required:
            root (arg): a pathlike object for root.
            This is the initial starting point.
        Optional:
            name (kwarg): Regular expression to be used for matching
            _type (kwarg): "f" for file; "d" for directory
            _hash (kwarg): Filepath for hash to check
            check_zips (kwarg): If True, archives will be searched, too
            ignore_errors (kwarg): Suppress OSErrors. Default is False
        """
        self.ignore_errors = bool(ignore_errors)
        self.check_hash = True if _hash else False
        self.check_zips = bool(check_zips)
        self.name_re = name
        self._type = _type
        await self.paths_queue.put(root)
        try:
            cpus = len(os.sched_getaffinity(0))
        except AttributeError:
            cpus = os.cpu_count()
        async with curio.TaskGroup() as producers:
            await producers.spawn(self.crawler)
            if _hash:
                self.master_hash = generate_hash(name)
            async with curio.TaskGroup() as consumers:
                if self.check_zips:
                    for _ in range(cpus):
                        await consumers.spawn(self.search_zips)
                for _ in range(cpus * 5):
                    await consumers.spawn(self.search)
                for _ in range(cpus * 10):
                    await producers.spawn(self.crawler)
                try:
                    await self.paths_queue.join()
                    await producers.cancel_remaining()
                    await self.items_queue.join()
                    if self.check_zips:
                        await self.zip_paths_queue.join()
                    await consumers.cancel_remaining()
                except (KeyboardInterrupt, Exception):
                    self.__cancelled = True
                    await producers.cancel_remaining()
                    await consumers.cancel_remaining()

    async def scan(self, root):
        """
        Producer for both the self.paths_queue and self.items_queue

        Required:
            root (arg): a pathlike object to scan with scandir
        """
        try:
            with os.scandir(root) as scanner:
                for entry in scanner:
                    is_dir = await check_if_dir(entry)
                    if is_dir:
                        await self.paths_queue.put(entry.path)
                    elif self.check_zips:
                        is_zip = await check_if_zip(entry)
                        if is_zip:
                            await self.zip_paths_queue.put(entry)
                    await self.items_queue.put(entry)
        except OSError as e:
            if not self.ignore_errors:
                print(e)
        except (KeyboardInterrupt, Exception):
            self.__cancelled = True
            return

    async def crawler(self):
        """
        Initiator for the producer, `scan`

        Should not be interacted with directly.
        """
        while not self.__cancelled:
            item = None
            crawl_task = None
            try:
                item = await self.paths_queue.get()
                crawl_task = await curio.spawn(self.scan, item)
                await crawl_task.wait()
            except (KeyboardInterrupt, Exception):
                self.__cancelled = True
                if crawl_task is not None:
                    await crawl_task.cancel()
                return
            finally:
                if crawl_task is not None:
                    await crawl_task.join()
                if item is not None:
                    await self.paths_queue.task_done()

    async def search(self):
        """
        Consumer for self.items_queue.

        Should not be interacted with directly.
        """
        while not self.__cancelled:
            item = None
            try:
                item = await self.items_queue.get()
                is_match = await self.match(item)
                if is_match:
                    await self.callback(item.path)
            except (KeyboardInterrupt, Exception):
                self.__cancelled = True
                return
            finally:
                if item is not None:
                    await self.items_queue.task_done()

    async def search_zips(self):
        """
        Consumer for self.zip_paths_queue.

        Should not be interacted with directly.
        """
        while True:
            item = await self.zip_paths_queue.get()
            results = await curio.run_in_process(
                search_zipfile,
                item.path,
                self.name_re,
                self.check_hash,
                self.master_hash,
            )
            for result in results:
                await self.callback(result)
            await self.zip_paths_queue.task_done()

    async def match(self, entry):
        """
        Checks PathLike entry against specified filters. Returns entry if match
        is found; else, None.

        Required:
            entry (arg): PathLike object to test against
        """
        if self._type == 'd':
            is_dir = await check_if_dir(entry)
            if is_dir and self.name_re.match(entry.name):
                return entry
        elif self._type == 'f':
            is_file = await check_if_file(entry)
            if is_file:
                if self.check_hash:
                    f_hash = await curio.run_in_process(
                        generate_hash, entry.path
                    )
                    if f_hash == self.master_hash:
                        return entry
                else:
                    if self.name_re.match(entry.name):
                        return entry
        else:
            if self.check_hash:
                is_file = await check_if_file(entry)
                if is_file:
                    f_hash = await curio.run_in_process(
                        generate_hash, entry.path
                    )
                    if f_hash == self.master_hash:
                        return entry
            elif self.name_re.match(entry.name):
                return entry


def generate_hash(path):
    """
    Generates an MD5 hash for the specified file

    Required:
        path (arg): A filepath or a PathLike object
    """
    with open(path, 'rb') as f:
        f_hash = hashlib.md5()
        while chunk := f.read(8192):
            f_hash.update(chunk)
    return f_hash.digest()


def generate_zip_hash(path):
    """
    Generates an MD5 hash for the specified file

    Required:
        path (arg): A filepath or a PathLike object from a ZIP
    """
    with path.open('rb') as f:
        f_hash = hashlib.md5()
        while chunk := f.read(8192):
            f_hash.update(chunk)
    return f_hash.digest()


def search_zipfile(zip_name, name_re, check_hash, master_hash):
    """
    Returns a list of matched items

    Required:
        zip_name (arg): ZIP-like object path
        name_Re (arg): Regex to match
        check_hash (arg): A Boolean to check for file hashes
        mster_hash (arg): The hash to check further files against
    """
    results = []
    zip_obj = zipfile.Path(zip_name)
    for item in iter_zip(zip_obj):
        if check_hash:
            if item.is_file():
                f_hash = generate_zip_hash(item)
                if f_hash == master_hash:
                    results.append(str(zip_obj.joinpath(item.name)))
        else:
            if re.match(name_re, item.name):
                results.append(str(zip_obj.joinpath(item.name)))
    return results


def iter_zip(zip_obj, path=''):
    p = zip_obj.joinpath(path)
    for i in p.iterdir():
        if i.is_dir():
            yield from iter_zip(zip_obj, i.at)  # ".at" is undocumented
        yield i


async def check_if_file(entry):
    return entry.is_file()


async def check_if_dir(entry):
    return entry.is_dir()


async def check_if_zip(entry):
    return zipfile.is_zipfile(entry.path)


async def async_print(*args, **kwargs):
    print(*args, **kwargs)


def clean_re_chars(name):
    # TODO: Make this handle the full gambit of re special chars
    return '^' + name.replace('.', '\\.').replace('*', '.*') + "$"


async def main():
    import argparse
    import textwrap

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description=textwrap.dedent('''
Simple, striped down `find` replacement for use on NAS or slow disk drives.
Results may be faster than `find` on SSDs for deep but not shallow searches.
\nThe "-z/--zips" flag will allow you to search inside zip-like objects.
\nThe "--hash" option accepts an absolute filepath to generate a has to search.
        ''')
    )
    parser.add_argument(
            'path',
            nargs='?',
            help='Root location for the search. Default is cwd.',
        )
    name_group = parser.add_mutually_exclusive_group()
    name_group.add_argument(
            '-name',
            help='Case sensitive search. Accepts basic regular expressions.'
        )
    name_group.add_argument(
            '-iname',
            help='Case insensitive search. Accepts basic regular expressions.'
        )
    name_group.add_argument(
            '--hash',
            default=False,
            help='Flag for searching in archives. Default is False.',
        )
    parser.add_argument(
            '-type',
            choices=['d', 'f'],
            help='"f" for file; "d" for directory. Ignore for either.',
        )
    parser.add_argument(
            '-z',
            '--zips',
            action='store_true',
            default=False,
            help='Flag for searching in archives. Default is False.',
        )
    parser.add_argument(
            '--ignore_errors',
            action='store_true',
            default=False,
            help='Flag for suppressing OSErrors. Default is False.',
        )
    args = parser.parse_args()

    path = args.path if args.path else os.getcwd()
    if args.name:
        name = re.compile(clean_re_chars(args.name))
    elif args.iname:
        name = re.compile(clean_re_chars(args.iname), re.IGNORECASE)
    elif args.hash:
        name = args.hash
    else:
        name = re.compile(r'.*')
    kwargs = {
            'name': name,
            '_type': args.type,
            'ignore_errors': args.ignore_errors,
            'check_zips': args.zips,
            '_hash': args.hash,
        }
    find = Nidf()
    try:
        await find(path, **kwargs)
    except (KeyboardInterrupt, Exception):
        pass


if __name__ == '__main__':
    with curio.Kernel() as kernel:
        kernel.run(main, shutdown=True)
