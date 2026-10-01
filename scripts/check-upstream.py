"""Read-only live contract smoke test. Never substitutes fixtures."""
import asyncio
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
key_file=Path(__file__).resolve().parents[1]/'secrets.test/mexicodev_api_key.txt'
if key_file.exists() and not os.getenv('MEXICODEV_API_KEY'):
    os.environ['MEXICODEV_API_KEY']=key_file.read_text().strip()
from app.feed import Feed

async def main():
    feed=Feed('live')
    try:
        catalog=await feed.catalog(force=True)
        assert not catalog['stale']
        status=await feed.request('status')
        rows=catalog['jobs']
        sample=rows[::max(1,len(rows)//40)][:40]
        for job in sample:
            detail=await feed.detail(job['id'])
            assert detail['id']==job['id']
            evidence={e['id']:e for e in detail['evidence']}
            references={i for d in detail['dimensions'].values() for i in d['evidence_ids']}
            references.update(i for field in detail['fields'].values() for i in field.get('evidence_ids',[]))
            assert references<=evidence.keys(), 'Unresolved evidence reference'
            for e in evidence.values():
                assert detail['description_text'][e['start']:e['end']]==e['text'], 'Evidence offsets mismatch'
        for comparison in ('completed','elapsed','all'):
            market=await feed.market(comparison)
            for month in market['months']:
                if not month['counts']:continue
                skill=max(month['counts'],key=month['counts'].get)
                records=await feed.market_jobs({'month':month['month'],'skill':skill,'comparison':comparison,'limit':25})
                assert records['total']==month['counts'][skill], 'Market count changed or mismatched; retry against a stable snapshot'
                assert records['jobs'], 'Missing drilldown jobs'
        print(f"Live catalog connected: {len(catalog['jobs'])} retained jobs; version {catalog['version']}")
        print(f"Upstream stale: {bool(status.get('stale'))}; ingestion pause: {status.get('ingestion_paused_reason') or 'none'}")
        print(f"Evidence records checked: {len(sample)}; market comparisons checked: 3")
        if not catalog['jobs']:
            print('No published records: detail/evidence compatibility remains unverified.')
    finally:
        await feed.client.aclose()

asyncio.run(main())
