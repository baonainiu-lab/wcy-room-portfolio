#!/usr/bin/env python3
"""UNUSED EXPERIMENT: receiver-partition assembly was superseded before use.

Status: pending_unused. Only tiny synthetic CPU tests were run. No actual 4K
partition arrays were read or assembled. The approved Room19 production route
uses full-atlas offline Blender CLI bakes after repeated MCP 120 s timeouts.
Production invocation below is deliberately disabled; retain as review history.

Original design: assemble MCP receiver partitions without adding light.

Example (only after the MCP/CPU handoff window is granted):
  python scripts/assemble-room-v19-light.py --state day --slot 2 --parts 2
Small CPU tests: python scripts/assemble-room-v19-light.py --self-test

Each true UV core is copied bit for bit. Existing margin pixels are selected
from the eligible partition with the nearest core (exact Euclidean distance);
ties choose the lowest partition index. No color averaging or summation occurs.
"""
import argparse
import ast
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import zlib

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PREPARED_SHA = '45e258c586f5bc46203ca1d3ff6be14cfde72fcc28a40ec919040fcee9a9cd64'
PARTS = ROOT / 'assets/blender/linear-intermediates/lighting-v19-partitions'
HELPER = ROOT / 'assets/blender/scripts/room_v19_partitioned_bake.py'
ENCODER = ROOT / 'assets/blender/scripts/pbr_bake_channels.py'
LIGHT_SIZES = [4096]*6 + [3072, 2048, 3072, 4096, 4096, 3072, 1024]
PASS_FILTER = ['DIRECT', 'INDIRECT', 'COLOR', 'DIFFUSE', 'EMIT']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, data):
    pending = Path(path).with_suffix('.json.tmp')
    pending.write_text(json.dumps(data, indent=2, ensure_ascii=False)+'\n')
    pending.replace(path)


def checked(path, digest, expected=None):
    path = ROOT / path
    require(path.is_file(), f'Missing input: {path}')
    if expected is not None:
        require(path.resolve() == Path(expected).resolve(), f'Unexpected input path: {path}')
    require(sha(path) == digest, f'Input SHA256 mismatch: {path}')
    return path


# Exact squared Euclidean distance transform, separable lower envelopes of
# parabolas. Integer distances are exact at atlas sizes; doubles are only used
# for envelope boundaries. This local CPU helper avoids a SciPy dependency.
EDT_C = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
static void edt(const int32_t *f, int n, int32_t *d, int *v, double *z) {
    int k=0; v[0]=0; z[0]=-INFINITY; z[1]=INFINITY;
    for(int q=1;q<n;q++) {
        double s=((double)f[q]+(double)q*q-f[v[k]]-(double)v[k]*v[k])/(2.0*(q-v[k]));
        while(s<=z[k]) {
            k--;
            s=((double)f[q]+(double)q*q-f[v[k]]-(double)v[k]*v[k])/(2.0*(q-v[k]));
        }
        k++;v[k]=q;z[k]=s;z[k+1]=INFINITY;
    }
    k=0;
    for(int q=0;q<n;q++) {while(z[k+1]<q) k++;int a=q-v[k];d[q]=a*a+f[v[k]];}
}
int main(int argc,char **argv) {
    if(argc!=5)return 2;
    int h=atoi(argv[1]),w=atoi(argv[2]);if(h<1||w<1||h>8192||w>8192)return 3;
    size_t n=(size_t)h*w;int cap=h>w?h:w;
    uint8_t *mask=malloc(n);int32_t *grid=malloc(n*sizeof(int32_t));
    int32_t *f=malloc(cap*sizeof(int32_t)),*d=malloc(cap*sizeof(int32_t));
    int *v=malloc(cap*sizeof(int));double *z=malloc((cap+1)*sizeof(double));
    if(!mask||!grid||!f||!d||!v||!z)return 4;
    FILE *in=fopen(argv[3],"rb");if(!in||fread(mask,1,n,in)!=n)return 5;fclose(in);
    for(int x=0;x<w;x++) {for(int y=0;y<h;y++)f[y]=mask[(size_t)y*w+x]?0:1000000000;
        edt(f,h,d,v,z);for(int y=0;y<h;y++)grid[(size_t)y*w+x]=d[y];}
    free(mask);
    FILE *out=fopen(argv[4],"wb");if(!out)return 6;
    for(int y=0;y<h;y++) {edt(grid+(size_t)y*w,w,d,v,z);if(fwrite(d,sizeof(int32_t),w,out)!=(size_t)w)return 7;}
    fclose(out);free(grid);free(f);free(d);free(v);free(z);return 0;
}
'''


def compile_edt(folder):
    compiler = shutil.which('clang') or shutil.which('cc')
    require(compiler is not None, 'An installed C compiler is required for exact CPU nearest-core distances.')
    source, binary = Path(folder)/'edt.c', Path(folder)/'edt'
    source.write_text(EDT_C)
    subprocess.run([compiler, '-O2', '-std=c11', str(source), '-o', str(binary), '-lm'],
                   check=True, capture_output=True, text=True)
    return binary


def distance_squared(core, executable, folder, index):
    require(core.dtype == np.bool_ and core.any(), 'Every receiver partition needs nonempty UV core coverage.')
    source, target = Path(folder)/f'core-{index}.bin', Path(folder)/f'distance-{index}.bin'
    core.astype(np.uint8).tofile(source)
    subprocess.run([str(executable), str(core.shape[0]), str(core.shape[1]), str(source), str(target)],
                   check=True, capture_output=True, text=True)
    result = np.memmap(target, dtype=np.int32, mode='r', shape=core.shape)
    require(np.all(result[core] == 0), 'Distance transform did not preserve core zeros.')
    return result


def load_parts(state, slot, count):
    require(0 <= slot < 13 and count >= 2, 'Invalid slot/partition count.')
    prepared_path = ROOT/'assets/blender/photoreal-materials-v19-prepared.json'
    prepared = read(prepared_path)
    require(prepared['complete'] and prepared['sha256'] == PREPARED_SHA, 'Current reviewed source contract changed.')
    checked(prepared['derivative'], PREPARED_SHA)
    # The prepared scene manifest is produced through MCP and binds the exact
    # source. Matching its complete baked-node list catches a missing receiver
    # even if all partition manifests repeat the same incomplete list.
    expected_meshes = sorted(name for name in prepared['existingGeometryAfter'] if name.endswith(f'__baked__A{slot}'))
    require(expected_meshes, 'No current-source receiver list for the requested atlas.')
    recipes = {row['path']: row['sha256'] for row in prepared['recipeFiles']}
    checked(ENCODER, recipes['assets/blender/scripts/pbr_bake_channels.py'])
    checked(ROOT/'assets/blender/scripts/photoreal_materials_v19.py', recipes['assets/blender/scripts/photoreal_materials_v19.py'])
    helper_sha = sha(HELPER)
    size = LIGHT_SIZES[slot]
    records, arrays, cores, file_evidence = [], [], [], []
    for index in range(count):
        key = f'{state}-{slot}-part{index}of{count}'
        manifest_path = PARTS/(key+'.json')
        require(manifest_path.is_file(), f'Await completed partition manifest: {manifest_path}')
        record = read(manifest_path)
        intro = state == 'intro'
        require(record['complete'] and record['sourceSha256'] == PREPARED_SHA and record['slot'] == slot and
                record['part'] == index and record['partCount'] == count and record['samples'] == 96 and
                record['dimensions'] == [size, size] and record['state'] == ('day' if intro else state) and
                record['cleanIntro'] == record['receiverOnly'] == intro, f'Invalid partition contract: {key}')
        require(record['fullSceneShadowsAndGiRetained'] and record['geometryUvNormalsUnchanged'] and
                record['glossyExcluded'] and record['passFilter'] == PASS_FILTER and record['margin'] == max(8, round(size/256)),
                f'Lighting/geometry/margin contract changed: {key}')
        require(record['helperSha256'] == helper_sha and Path(record['helperPath']).resolve() == HELPER.resolve(),
                'Partition helper changed; do not mix implementations.')
        require((ROOT/record['sourceBlend']).resolve() == (ROOT/prepared['derivative']).resolve(), 'Unexpected partition Blender source.')
        require(record['format'] == 'float32 RGBA .npy; Blender bottom-up, unquantized scene-linear', 'Unexpected partition numeric format.')
        path = checked(record['path'], record['sha256'], PARTS/(key+'.npy'))
        coverage_path = checked(record['coverage']['path'], record['coverage']['sha256'], PARTS/(key+'-coverage.npz'))
        require(record['coverage']['method'] == 'Original BakeUV triangle pixel-center rasterization', 'Wrong core coverage rasterizer.')
        array = np.load(path, mmap_mode='r', allow_pickle=False)
        require(array.dtype == np.float32 and array.shape == (size, size, 4) and np.isfinite(array).all(),
                f'Partition contains invalid/non-float32 pixels: {key}')
        with np.load(coverage_path, allow_pickle=False) as data:
            require(data.files == ['coverage'], 'Unexpected coverage archive contents.')
            raw_core = data['coverage']
        require(raw_core.shape == (size, size) and raw_core.dtype in (np.dtype('uint8'), np.dtype('bool')) and
                np.all((raw_core == 0) | (raw_core == 1)), 'Coverage is not a binary pixel-center mask.')
        core = raw_core.astype(bool)
        alpha = array[..., 3]
        occupied = alpha > .5
        require(core.any() and int(core.sum()) == record['coverage']['pixels'], 'Core coverage count mismatch.')
        require([float(alpha.min()), float(alpha.max())] == record['alphaRange'] and alpha.min() >= 0 and alpha.max() <= 1,
                'Partition alpha statistics are invalid.')
        missing = int(np.sum(core & ~occupied))
        require(missing == record['corePixelsWithoutAlpha'] == 0,
                f'{key}: {missing} true UV core pixels have no baked alpha; cannot assemble losslessly.')
        require(int(occupied.sum()) == record['alphaOccupiedPixels'] and
                float(array[..., :3].max()) == record['sourceRadianceMaximum'], 'Partition recorded pixel statistics differ.')
        require(np.all(array[alpha == 0, :3] == 0), f'{key}: nonzero radiance exists outside alpha coverage; refusing to discard it.')
        records.append(record); arrays.append(array); cores.append(core)
        file_evidence += [dict(path=str(manifest_path), sha256=sha(manifest_path)), dict(path=str(path), sha256=record['sha256']),
                          dict(path=str(coverage_path), sha256=record['coverage']['sha256'])]
    first = records[0]
    groups = first['partitions']
    require(len(groups) == count and all(groups) and all(isinstance(name, str) for group in groups for name in group), 'Invalid receiver grouping.')
    flattened = [name for group in groups for name in group]
    require(len(flattened) == len(set(flattened)) and sorted(flattened) == expected_meshes,
            'Receiver groups are not mutually exclusive and complete for the prepared atlas.')
    require(len(first['meshSignature']) == 64 and len(first['partitionUvAreas']) == count and
            all(math.isfinite(area) and area > 0 for area in first['partitionUvAreas']), 'Invalid geometry signature/UV areas.')
    for record in records:
        require(record['partitions'] == groups and record['partitionUvAreas'] == first['partitionUvAreas'] and
                record['meshSignature'] == first['meshSignature'], 'Parts disagree on grouping, UV areas or complete receiver signature.')
    proof_path = ROOT/'assets/blender/room-v19-surface-reuse-proof.json'
    proof = read(proof_path)
    require(proof['sourceSha256'] == PREPARED_SHA, 'Current independent receiver geometry proof is stale.')
    surface = next((row for row in proof['surfaces'] if row['slot'] == slot), None)
    if surface:
        require(first['meshSignature'] == surface['geometryUvNormalsSignature'], 'Partition signature differs from independently inspected source geometry.')
    else:
        raise ValueError('This CPU assembler currently accepts only atlases with independent current-source mesh signatures; obtain an MCP proof for this changed/new atlas first.')
    return prepared, records, arrays, cores, file_evidence, dict(path=str(proof_path), sha256=sha(proof_path))


def compose(arrays, cores, margin, folder, executable):
    shape = arrays[0].shape
    require(all(array.shape == shape for array in arrays) and all(core.shape == shape[:2] for core in cores), 'Partition dimensions differ.')
    output_path = Path(folder)/'assembled-linear-rgba.npy'
    output = np.lib.format.open_memmap(output_path, mode='w+', dtype=np.float32, shape=shape)
    output[:] = 0
    union = np.zeros(shape[:2], dtype=bool)
    owner = np.full(shape[:2], -1, dtype=np.int16)
    overlaps = 0
    for index, (array, core) in enumerate(zip(arrays, cores)):
        shared_core = union & core
        if shared_core.any():
            require(np.array_equal(output[shared_core].view(np.uint32), array[shared_core].view(np.uint32)),
                    f'Partition {index} has conflicting true UV core pixels; a single atlas cannot preserve both.')
            overlaps += int(shared_core.sum())
        fresh_core = core & ~union
        output[fresh_core] = array[fresh_core]
        owner[fresh_core] = index
        union |= core
    best = np.full(shape[:2], np.iinfo(np.int32).max, dtype=np.int32)
    margin_counts, alpha_union = [], union.copy()
    contested_margin = np.zeros(shape[:2], dtype=bool)
    seen_margin = np.zeros(shape[:2], dtype=bool)
    for index, (array, core) in enumerate(zip(arrays, cores)):
        occupied = array[..., 3] > 0
        alpha_union |= occupied
        distances = distance_squared(core, executable, folder, index)
        maximum_distance = int(distances[occupied].max()) if occupied.any() else 0
        # A 16px raster dilation may use Chebyshev neighborhoods. This generous
        # support bound catches incorrectly opaque cleared images, without
        # assuming that Blender's margin stencil is Euclidean.
        require(maximum_distance <= 2*(margin+2)**2,
                f'Partition {index} has alpha coverage far outside its declared margin ({math.sqrt(maximum_distance):.3f}px).')
        candidate = occupied & ~union
        contested_margin |= seen_margin & candidate
        seen_margin |= candidate
        selected = candidate & (distances < best)
        output[selected] = array[selected]
        owner[selected] = index
        best[selected] = distances[selected]
        margin_counts.append(dict(part=index, alphaSupportPixels=int(occupied.sum()), corePixels=int(core.sum()),
                                  maximumAlphaDistanceToCorePixels=math.sqrt(maximum_distance)))
        del distances
    require(np.array_equal(owner >= 0, alpha_union), 'Composition lost covered core or margin pixels.')
    for index, (array, core) in enumerate(zip(arrays, cores)):
        require(np.array_equal(output[core].view(np.uint32), array[core].view(np.uint32)),
                f'Partition {index} core floats were not preserved bit for bit.')
    output.flush()
    return output, dict(corePixels=int(union.sum()), sharedCorePixelsWithIdenticalFloatBits=overlaps,
                        coveredPixels=int(alpha_union.sum()), chosenMarginPixels=int((alpha_union & ~union).sum()),
                        contestedMarginPixels=int(contested_margin.sum()), outputZeroPixels=int((~alpha_union).sum()),
                        ownerPixelCounts=[int(np.sum(owner == i)) for i in range(len(arrays))], parts=margin_counts,
                        coreFloatsBitExactlyPreserved=True, radianceSummed=False, radianceAveraged=False,
                        marginPolicy='Among partitions with positive-alpha data, choose minimum exact squared Euclidean distance to that partition core; lowest part index breaks ties. Every true core overrides every margin.')


def encoding_functions(fake_file=None):
    """Load only the original pure encoder functions; never import bpy."""
    source = ast.parse(ENCODER.read_text(), filename=str(ENCODER))
    names = {'_chunk', '_png', 'write_rgbm32'}
    selected = [node for node in source.body if isinstance(node, ast.FunctionDef) and node.name in names]
    require({node.name for node in selected} == names, 'Original RGBM32 encoder functions are unavailable.')
    namespace = dict(np=np, Path=Path, struct=struct, zlib=zlib, hashlib=hashlib, RGBM_RANGE=32.0,
                     __file__=str(fake_file or ENCODER))
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(ENCODER), 'exec'), namespace)
    return namespace


def assemble(state, slot, count):
    started = time.monotonic()
    prepared, records, arrays, cores, evidence, geometry_proof = load_parts(state, slot, count)
    folder = ROOT/('public/textures/intro-clean-v19' if state == 'intro' else 'public/textures/lighting-v19')
    prefix = 'day' if state == 'intro' else state
    output = folder/f'{prefix}-{slot}.png'
    manifest_path = folder/f'{prefix}-{slot}-manifest.json'
    if manifest_path.exists():
        old = read(manifest_path)
        require(old.get('partitionAssembly', {}).get('inputFiles') == evidence,
                'A different completed bake already occupies this output; refusing an implicit replacement.')
        checked(output, old['sha256'])
        return old
    with tempfile.TemporaryDirectory(prefix='room19-light-assembly-') as temporary:
        executable = compile_edt(temporary)
        pixels, coverage = compose(arrays, cores, records[0]['margin'], temporary, executable)
        for record in evidence:
            checked(record['path'], record['sha256'])
        checked(prepared['derivative'], PREPARED_SHA)
        checked(HELPER, records[0]['helperSha256'])
        result = encoding_functions()['write_rgbm32'](output, pixels)
        result.update(complete=True, slot=slot, state=prefix, engine='CYCLES', samples=96, passFilter=PASS_FILTER,
                      glossyExcluded=True, geometryUvNormalsUnchanged=True, seconds=round(sum(r['seconds'] for r in records), 2),
                      sourceBlend=records[0]['sourceBlend'], sourceSha256=PREPARED_SHA,
                      cleanIntro=state == 'intro', receiverOnly=state == 'intro',
                      partitionAssembly=dict(complete=True, version=1, inputFiles=evidence, partCount=count,
                          partitions=records[0]['partitions'], partitionUvAreas=records[0]['partitionUvAreas'],
                          meshSignature=records[0]['meshSignature'], independentGeometryProof=geometry_proof,
                          helperPath=str(HELPER), helperSha256=records[0]['helperSha256'],
                          assemblerPath=str(Path(__file__).resolve()), assemblerSha256=sha(__file__),
                          encoderPath=str(ENCODER), encoderSha256=sha(ENCODER), originalRgbm32EncoderUsedVerbatim=True,
                          unquantizedBottomUpFloatPartitions=True, fullSceneShadowsAndGiRetained=True,
                          samplesPerReceiver=96, margin=records[0]['margin'], coverage=coverage,
                          assemblySeconds=round(time.monotonic()-started, 2),
                          limitations='Exact preservation of each partition core buffer, not a bitwise comparison with a monolithic stochastic Cycles bake. Margin ownership is explicitly nearest-core.'))
        # A completed manifest is published last; partial output is never ready.
        checked(prepared['derivative'], PREPARED_SHA)
        write(manifest_path, result)
    return result


def self_test():
    with tempfile.TemporaryDirectory(prefix='room19-assembly-test-') as temporary:
        executable = compile_edt(temporary)
        rng = np.random.default_rng(19)
        for index, shape in enumerate(((1, 7), (7, 1), (9, 11), (17, 13))):
            core = rng.random(shape) < .2
            core.flat[0] = True
            actual = distance_squared(core, executable, temporary, f'test-{index}')
            y, x = np.indices(shape)
            coordinates = np.argwhere(core)
            expected = np.min(np.stack([(y-cy)**2+(x-cx)**2 for cy, cx in coordinates]), axis=0)
            require(np.array_equal(actual, expected), 'Exact EDT differs from brute-force squared distance.')
        cores = [np.zeros((9, 11), bool) for _ in range(2)]
        cores[0][4, 2] = True; cores[1][4, 8] = True
        arrays = [np.zeros((9, 11, 4), np.float32) for _ in range(2)]
        arrays[0][:] = (2.25, 3.5, 4.75, 1); arrays[1][:] = (11.125, 12.5, 48.25, 1)
        output, detail = compose(arrays, cores, 16, temporary, executable)
        require(np.array_equal(output[4, 2], arrays[0][4, 2]) and np.array_equal(output[4, 8], arrays[1][4, 8]), 'Core priority failed.')
        require(np.array_equal(output[4, 5], arrays[0][4, 5]) and np.array_equal(output[4, 6], arrays[1][4, 6]), 'Nearest core/tie policy failed.')
        original = output.copy()
        changed = [core.copy() for core in cores]; changed[1][4, 2] = True
        try:
            compose(arrays, changed, 16, temporary, executable)
        except ValueError as error:
            require('conflicting true UV core' in str(error), 'Unexpected conflict test error.')
        else:
            raise ValueError('Conflicting core values were silently accepted.')
        functions = encoding_functions(Path(temporary)/'scripts/pbr_bake_channels.py')
        record = functions['write_rgbm32'](Path(temporary)/'textures/test.png', original)
        require(record['hdrOutliers']['count'] > 0 and record['sourceRadianceMaximum'] == 48.25, 'HDR overflow was lost.')
        with np.load(record['hdrOutliers']['path'], allow_pickle=False) as sidecar:
            flat = original[..., :3].reshape(-1)
            require(np.array_equal(sidecar['indices'], np.flatnonzero(flat > 32)) and
                    np.array_equal(sidecar['values'].view(np.uint32), flat[sidecar['indices']].view(np.uint32)), 'HDR indices/float bits changed.')
        from PIL import Image
        with Image.open(record['path']) as image:
            encoded = np.asarray(image)
        # Compare directly to the authoritative writer's expected bottom-up
        # source mapping, with deliberately asymmetric rows.
        asymmetric = np.zeros((3, 4, 4), np.float32)
        asymmetric[0, 0, :3] = (1, 2, 3); asymmetric[-1, 0, :3] = (4, 5, 6)
        flip_record = functions['write_rgbm32'](Path(temporary)/'textures/flip.png', asymmetric)
        with Image.open(flip_record['path']) as image:
            a = np.asarray(image).astype(np.float32)/255
        recovered = a[..., :3]*a[..., 3:4]*32
        require(np.max(np.abs(recovered[0, 0]-(4, 5, 6))) < .03 and np.max(np.abs(recovered[-1, 0]-(1, 2, 3))) < .03,
                'PNG orientation is not bottom-up flipped exactly once.')
    return dict(complete=True, scope='small CPU synthetic tests only', exactEdtMatchesBruteForce=True,
                corePriorityAndBitPreservation=True, nearestMarginAndDeterministicTie=True, conflictingCoresRejected=True,
                hdrFloatBitsAndBottomUpIndicesPreserved=True, pngOrientationVerified=True, realPartitionAssetsRead=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', choices=('day', 'night', 'intro'))
    parser.add_argument('--slot', type=int)
    parser.add_argument('--parts', type=int, default=2)
    parser.add_argument('--self-test', action='store_true')
    arguments = parser.parse_args()
    if not arguments.self_test and (arguments.state is None or arguments.slot is None):
        parser.error('--state and --slot are required for actual assembly.')
    try:
        require(arguments.self_test, 'Partition assembly is pending_unused and disabled; Room19 uses the approved full-atlas CLI bake fallback.')
        result = self_test() if arguments.self_test else assemble(arguments.state, arguments.slot, arguments.parts)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        print(json.dumps(dict(complete=False, status='assembly_blocked', errorType=type(error).__name__, error=str(error)), indent=2))
        sys.exit(1)
