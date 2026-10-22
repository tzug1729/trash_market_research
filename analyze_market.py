"""PBL1 trash-bin data: nullable loading, descriptive summaries, optional plots."""
from pathlib import Path
import argparse,json
import pandas as pd

def load_products(data_dir):
    schema=json.loads((data_dir/'schema.json').read_text(encoding='utf8'))
    frames=[]
    for env in ['indoor','outdoor']:
        df=pd.read_csv(data_dir/f'{env}_products.csv',encoding='utf-8-sig',dtype='string',keep_default_na=False,na_values=[''])
        for field in schema:
            if field['dtype']in ['Int64','Float64']:
                df[field['field']]=pd.to_numeric(df[field['field']],errors='raise').astype(field['dtype'])
        if not df['product_id'].is_unique:raise ValueError(f'Duplicate product_id: {env}')
        if not df['environment'].eq(env).all():raise ValueError(f'Wrong environment: {env}')
        frames.append(df)
    data=pd.concat(frames,ignore_index=True)
    if not data['product_id'].is_unique:raise ValueError('Duplicate IDs across files')
    return data

def summarize(data,out):
    out.mkdir(parents=True,exist_ok=True)
    counts=[];coverage=[]
    for env,group in data.groupby('environment',sort=True):
        for field in ['opening_shape','opening_count','lid_type','use_category','opening_shape_basis']:
            for value,n in group[field].astype('string').fillna('未確認').value_counts(dropna=False).items():
                counts.append({'environment':env,'field':field,'value':value,'count':int(n),'denominator':len(group)})
        for field in group.columns:
            coverage.append({'environment':env,'field':field,'confirmed':int(group[field].notna().sum()),'missing':int(group[field].isna().sum()),'total':len(group)})
    pd.DataFrame(counts).to_csv(out/'category_counts.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(coverage).to_csv(out/'missingness.csv',index=False,encoding='utf-8-sig')
    data.groupby('environment')[['capacity_l','price_jpy_tax_incl','body_height_mm']].describe().to_csv(out/'numeric_description.csv',encoding='utf-8-sig')
    data.loc[data['opening_dimension_status'].eq('confirmed')].to_csv(out/'opening_dimensions_confirmed.csv',index=False,encoding='utf-8-sig')
    return counts,coverage

def plot(data,out):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib import font_manager
    except ImportError as e:
        raise SystemExit('グラフ作成には matplotlib が必要です。pip install matplotlib を実行してください。')from e
    fonts={f.name for f in font_manager.fontManager.ttflist}
    for font in ['Yu Gothic','Meiryo','Noto Sans CJK JP','IPAexGothic','MS Gothic']:
        if font in fonts:plt.rcParams['font.family']=font;break
    plt.rcParams['axes.unicode_minus']=False
    titles={'indoor':'室内用','outdoor':'屋外用'}
    for env,g in data.groupby('environment'):
        for field,label in [('opening_shape','開口部形状'),('lid_type','フタ方式')]:
            c=g[field].fillna('未確認').value_counts().sort_values()
            fig,ax=plt.subplots(figsize=(9,max(4,len(c)*.42)))
            colors=['#aeb8c5'if x=='未確認'else'#2b6687'for x in c.index]
            ax.barh(c.index,c.values,color=colors)
            ax.bar_label(ax.containers[0],padding=3)
            ax.set(xlabel='収録事例数（市場シェアではありません）',title=f'{titles[env]}：{label}（n={len(g)}、未確認を含む）')
            ax.spines[['top','right']].set_visible(False)
            ax.margins(x=.15)
            fig.tight_layout()
            for ext in ['png','svg']:fig.savefig(out/f'{env}_{field}.{ext}',dpi=180,bbox_inches='tight')
            plt.close(fig)
        capacities=g['capacity_l'].dropna().astype(float)
        if not capacities.empty:
            fig,ax=plt.subplots(figsize=(9,4))
            bins=[0,5,10,15,20,30,45,70,100,200,500]
            categorized=pd.cut(capacities,bins=bins,right=True,include_lowest=True).value_counts(sort=False)
            ax.bar(range(len(categorized)),categorized.values,color='#2b6687')
            ax.set_xticks(range(len(categorized)),[str(x)for x in categorized.index],rotation=35,ha='right')
            ax.set(xlabel='容器容量の区間 [L]（対応袋容量とは別）',ylabel='事例数',title=f'{titles[env]}：容量（確認 {len(capacities)}/{len(g)}件）')
            fig.tight_layout()
            for ext in ['png','svg']:fig.savefig(out/f'{env}_capacity.{ext}',dpi=180,bbox_inches='tight')
            plt.close(fig)
        keys=['capacity_l','price_jpy_tax_incl','body_height_mm','opening_shape','opening_dimension_status','review_summary']
        values=[(g[k].eq('confirmed').sum()if k=='opening_dimension_status'else g[k].notna().sum())/len(g)*100 for k in keys]
        fig,ax=plt.subplots(figsize=(9,4))
        labels=['容器容量','税込価格','本体高さ','開口形状','開口寸法','レビュー要約']
        ax.barh(labels,values,color='#2b6687');ax.set(xlim=(0,105),xlabel='確認できた収録事例の割合 [%]',title=f'{titles[env]}：情報の確認率（n={len(g)}）')
        ax.bar_label(ax.containers[0],fmt='%.1f%%',padding=3)
        fig.tight_layout()
        for ext in ['png','svg']:fig.savefig(out/f'{env}_coverage.{ext}',dpi=180,bbox_inches='tight')
        plt.close(fig)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--output-dir',type=Path,default=None)
    parser.add_argument('--plot',action='store_true',help='matplotlibでPNG/SVGも出力')
    args=parser.parse_args();out=args.output_dir or args.data_dir/'analysis_output'
    data=load_products(args.data_dir);summarize(data,out)
    if args.plot:plot(data,out)
    print(json.dumps({'counts':data['environment'].value_counts().to_dict(),'output_dir':str(out)},ensure_ascii=True))

if __name__=='__main__':main()
