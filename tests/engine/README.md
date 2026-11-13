# Engine tests

`upstream/` contains the busted specs imported from `ajusa/VNDS-LOVE` tag `0.0.13`.

Expected full engine test command once LuaRocks tooling is installed:

```bash
alfons test
```

Current fallback structural verification command:

```bash
python tools/engine/verify_bootstrap.py
```

The fallback check verifies the imported source/test/build-file layout but does not execute MoonScript, busted, LÖVE, or lovebrew.
