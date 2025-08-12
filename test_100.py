import os
import re
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

def setup_korean_font():
    """
    matplotlib에서 한글을 지원하기 위한 폰트 설정을 시도합니다.
    """
    font_names = ['Malgun Gothic', 'AppleGothic', 'NanumGothic']
    for font_name in font_names:
        if any(font.name == font_name for font in fm.fontManager.ttflist):
            plt.rc('font', family=font_name)
            print(f"한글 폰트 '{font_name}'으로 설정되었습니다.")
            return
    
    print("경고: 'Malgun Gothic', 'AppleGothic', 'NanumGothic' 폰트를 찾을 수 없습니다. 그래프의 한글이 깨질 수 있습니다.")
    plt.rc('font', family='sans-serif')


def analyze_and_plot_logs(directory, selected_log_files):
    """
    선택된 로그 파일에서 각 Tact Time의 마지막 300개 측정치의 평균을 분석하고,
    결과를 표와 그래프로 생성합니다.

    Args:
        directory (str): 로그 파일이 있는 디렉토리 경로.
        selected_log_files (list): 사용자가 선택한 로그 파일 이름의 리스트.
    """
    tact_types_to_find = [
        "ProcessInput Tact", "copyInputToDevice Tact", "executeV2 Tact",
        "VerifyOutput Tact", "Infer Tact"
    ]
    pattern = re.compile(f"({'|'.join(re.escape(t) for t in tact_types_to_find)}) = (\\d+\\.?\\d*)")
    
    all_avg_results = []

    for filename in selected_log_files:
        file_path = os.path.join(directory, filename)
        print(f"'{filename}' 파일 분석 중...")
        
        file_tact_data = {tact_type: [] for tact_type in tact_types_to_find}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    match = pattern.search(line)
                    if match:
                        tact_name = match.group(1).strip()
                        tact_value = float(match.group(2))
                        if tact_name in file_tact_data:
                            file_tact_data[tact_name].append(tact_value)
        except Exception as e:
            print(f"'{filename}' 파일 처리 중 오류 발생: {e}")
            continue

        clean_filename = filename.replace('DLInfer_', '').replace('.log', '')
        for tact_name, values in file_tact_data.items():
            if not values:
                print(f"  - '{filename}'에서 '{tact_name}' 데이터를 찾을 수 없습니다.")
                continue

            last_300_values = values[-300:]
            average_value = sum(last_300_values) / len(last_300_values)
            print(f"  - '{tact_name}' 마지막 {len(last_300_values)}개 평균: {average_value:.2f} ms")

            all_avg_results.append({
                "model": clean_filename,
                "tact_type": tact_name,
                "tact_value": average_value
            })

    if not all_avg_results:
        print("분석할 로그 데이터가 없습니다.")
        return

    df = pd.DataFrame(all_avg_results)
    pivot_df = df.pivot_table(index='model', columns='tact_type', values='tact_value')
    
    # FPS 계산 (평균 Infer Tact 기반)
    if 'Infer Tact' in pivot_df.columns:
        pivot_df['FPS (avg)'] = 1000 / pivot_df['Infer Tact']
    
    display_cols = tact_types_to_find + ['FPS (avg)']
    existing_cols = [c for c in display_cols if c in pivot_df.columns]
    pivot_df = pivot_df[existing_cols]
    
    print("\n--- 최종 분석 결과 (마지막 300개 측정치 평균) ---")
    print(pivot_df.round(2))

    output_filename_csv = 'tact_summary_avg_last300.csv'
    pivot_df.to_csv(output_filename_csv, encoding='utf-8-sig')
    print(f"\n분석 결과가 '{output_filename_csv}' 파일로 저장되었습니다.")

    # --- 그래프 생성 ---
    print("\n그래프 생성 중...")
    for column_name in pivot_df.columns:
        plt.figure(figsize=(12, 7))
        bar_color = 'royalblue' if 'FPS' in column_name else 'skyblue'
        bars = plt.bar(pivot_df.index, pivot_df[column_name], color=bar_color)
        
        unit = " (FPS)" if 'FPS' in column_name else " (ms)"
        plt.title(f'모델별 평균 "{column_name}" 성능 비교', fontsize=16, pad=20)
        plt.suptitle('(로그 마지막 300회 측정 기준)', y=0.92, fontsize=10) # 부제목 추가
        plt.ylabel(f'평균 값{unit}', fontsize=12)
        plt.xlabel('모델', fontsize=12)
        plt.xticks(rotation=45, ha='right')
        
        for bar in bars:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2.0, yval, f'{yval:.1f}', va='bottom', ha='center', fontsize=10)

        plt.grid(axis='y', linestyle='--', alpha=0.7)
        plt.tight_layout(rect=[0, 0, 1, 0.9]) # 부제목 공간 확보
        
        safe_name = re.sub(r'[\\/*?:"<>|]', "", column_name).replace(' ', '_')
        output_filename_png = f'comparison_avg_{safe_name}.png'
        plt.savefig(output_filename_png)
        print(f"'{output_filename_png}' 그래프 저장 완료.")
    
    plt.show()

if __name__ == "__main__":
    setup_korean_font()
    log_directory = r"D:\AIV_LOG\Talos\2025_08\05"

    if not os.path.isdir(log_directory):
        print(f"오류: '{log_directory}' 경로 확인!!!!!!!")
    else:
        log_files = sorted([f for f in os.listdir(log_directory) if f.endswith(".log")])
        
        if not log_files:
            print(f"'{log_directory}' 디렉토리에 .log 파일이 없습니다.")
        else:
            print("분석할 로그 파일을 선택하세요 (ex : 1,3,5 또는 all):")
            for i, filename in enumerate(log_files):
                print(f"  {i+1}: {filename}")

            while True:
                try:
                    choice = input("> ")
                    if choice.lower() == 'all':
                        selected_files = log_files
                        break
                    selected_indices = [int(x.strip()) - 1 for x in choice.split(',')]
                    if all(0 <= i < len(log_files) for i in selected_indices):
                        selected_files = [log_files[i] for i in selected_indices]
                        break
                    else:
                        print("번호 이상함, 다시 입력 바람")
                except ValueError:
                    print("숫자, 쉼표(,), 또는 'all'만 입력 필요")

            if selected_files:
                analyze_and_plot_logs(log_directory, selected_files)