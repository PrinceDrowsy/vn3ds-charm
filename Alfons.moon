-- VN3DS-CHARM build tasks.
-- Imported from ajusa/VNDS-LOVE 0.0.13 and adapted so the engine source lives
-- under src/engine/ instead of an upstream root-level src/ directory.

engine_source = "src/engine"
compiled_engine = "build/engine/vnds"

tasks:
    clean: =>
        shfail "python tools/engine/compile_engine.py --clean" if fs.exists compiled_engine

    compile: =>
        shfail "python tools/engine/compile_engine.py"

    test: =>
        -- Runs upstream + project busted specs against MoonScript source directly.
        shfail "busted -C #{engine_source} --pattern=_spec ../../tests/engine"

    run: =>
        tasks.compile!
        shfail "love #{compiled_engine}"

    lovebrew: =>
        tasks.compile!
        shfail "python tools/engine/build_3dsx.py"
