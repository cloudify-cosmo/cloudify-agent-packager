Cloudify Agent Packager
=======================

Creates Cloudify agent packages.

Installation
~~~~~~~~~~~~

.. code:: shell

    pip install cloudify-agent-packager

For development:

.. code:: shell

    pip install https://github.com/cloudify-cosmo/cloudify-agent-packager/archive/master.tar.gz

Usage
~~~~~

Config yaml Explained
^^^^^^^^^^^^^^^^^^^^^

-  ``variables`` is a dict of variables you can use throughout the
   config (using the API, you can also send the dictionary rather the
   hard code it into the config.yaml, which is obviously the more common
   use case.) ``path``, ``match``, ``replace`` and ``with`` can all
   receive variables.
-  ``type`` is the files name you'd like to look for.
-  ``path`` is a regex path in which you'd like to search for files (so,
   for instance, if you only want to replace files in directory names
   starting with "my-", you would write "my-.\*")
-  ``base_directory`` is the directory from which you'd like to start
   the recursive search for files.
-  ``match`` is the initial regex based string you'd like to match
   before replacing the expression. This provides a more robust way to
   replace strings where you first match the exact area in which you'd
   like to replace the expression and only then match the expression you
   want to replace within it. It also provides a way to replace only
   specific instances of an expression, and not all.
-  ``replace`` - which regex expression would you like to replace?
-  ``with`` - what you replace with.
-  ``validate_before`` - a flag stating that you'd like to validate that
   the pattern you're looking for exists in the file and that all
   strings in ``must_include`` exists in the file as well.
-  ``must_include`` - as an additional layer of security, you can
   specify a set of regex based strings to look for to make sure that
   the files you're dealing with are the actual files you'd like to
   replace the expressions in.

In case you're providing a path to a file rather than a directory:

-  ``type`` and ``base_directory`` are depracated
-  you can provide a ``to_file`` key with the path to the file you'd
   like to create after replacing.
