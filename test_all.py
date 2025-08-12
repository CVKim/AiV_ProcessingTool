import os
import re
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

def setup_korean_font():
    """
    matplotlib에서 한글을 지원하기 위한 폰트 설정을 시도합니다.
    """
    # 윈도우, 맥OS, 리눅스에서 흔히 사용되는 한글 폰트 목록
    font_names = ['Malgun Gothic', 'AppleGothic', 'NanumGothic']
    for font_name in font_names:
        if any(font.name == font_name for font in fm.fontManager.ttflist):
            plt.rc('font', family=font_name)
            print(f"한글 폰트 '{font_name}'으로 설정되었습니다.")
            return
    
    # 위 폰트를 찾지 못한 경우 경고 메시지 출력
    print("경고: 'Malgun Gothic', 'AppleGothic', 'NanumGothic' 폰트를 찾을 수 없습니다. 그래프의 한글이 깨질 수 있습니다.")
    # 기본 폰트로 계속 진행
    plt.rc('font', family='sans-serif')


def analyze_and_plot_logs(directory, selected_log_files):
    """
    선택된 로그 파일에서 Tact Time을 분석하고, 결과를 표와 그래프로 생성합니다.

    Args:
        directory (str): 로그 파일이 있는 디렉토리 경로.
        selected_log_files (list): 사용자가 선택한 로그 파일 이름의 리스트.
    """
    # 분석할 Tact 종류 정의
    tact_types_to_find = [
        "ProcessInput Tact",
        "copyInputToDevice Tact",
        "executeV2 Tact",
        "VerifyOutput Tact",
        "Infer Tact"
    ]
    
    pattern = re.compile(f"({'|'.join(re.escape(t) for t in tact_types_to_find)}) = (\\d+\\.?\\d*)")
    
    all_results = []

    for filename in selected_log_files:
        file_path = os.path.join(directory, filename)
        print(f"'{filename}' 파일 분석 중...")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    match = pattern.search(line)
                    if match:
                        tact_name = match.group(1).strip()
                        tact_value = float(match.group(2))
                        # 그래프 레이블을 위해 파일명에서 불필요한 부분 제거
                        clean_filename = filename.replace('DLInfer_', '').replace('.log', '')
                        all_results.append({
                            "model": clean_filename,
                            "tact_type": tact_name,
                            "tact_value": tact_value
                        })
        except Exception as e:
            print(f"'{filename}' 파일 처리 중 오류 발생: {e}")

    if not all_results:
        print("분석할 로그 데이터가 없습니다.")
        return

    df = pd.DataFrame(all_results)
    pivot_df = df.pivot_table(index='model', columns='tact_type', values='tact_value')
    
    # 열 순서가 있다면 정리
    try:
        pivot_df = pivot_df[tact_types_to_find]
    except KeyError:
        print("경고: 일부 Tact 타입이 로그 파일에 존재하지 않을 수 있습니다.")


    print("\n--- 분석 결과 ---")
    print(pivot_df)

    output_filename_csv = 'tact_summary.csv'
    pivot_df.to_csv(output_filename_csv, encoding='utf-8-sig')
    print(f"\n분석 결과가 '{output_filename_csv}' 파일로 저장되었습니다.")

    # --- 그래프 생성 ---
    print("\n그래프 생성 중...")
    for tact_type in pivot_df.columns:
        plt.figure(figsize=(12, 7))
        bars = plt.bar(pivot_df.index, pivot_df[tact_type], color='skyblue')
        
        plt.title(f'모델별 "{tact_type}" 성능 비교', fontsize=16)
        plt.ylabel('Tact Time (ms)', fontsize=12)
        plt.xlabel('모델', fontsize=12)
        plt.xticks(rotation=45, ha='right') # 모델 이름이 길 경우를 대비해 레이블 회전
        
        # 막대 위에 값 표시
        for bar in bars:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2.0, yval, f'{yval:.1f}', va='bottom', ha='center')

        plt.grid(axis='y', linestyle='--', alpha=0.7)
        plt.tight_layout() # 레이아웃 최적화
        
        # 파일 이름으로 사용할 수 없는 문자 제거
        safe_tact_type_name = re.sub(r'[\\/*?:"<>|]', "", tact_type)
        output_filename_png = f'comparison_{safe_tact_type_name}.png'
        plt.savefig(output_filename_png)
        print(f"'{output_filename_png}' 그래프 저장 완료.")
    
    plt.show() # 모든 그래프를 화면에 표시

# --- 메인 실행 로직 ---
if __name__ == "__main__":
    # 한글 폰트 설정
    setup_korean_font()

    # 1. 로그 파일이 있는 폴더 경로를 설정하세요.
    log_directory = r"D:\AIV_LOG\Talos\2025_08\05"

    if not os.path.isdir(log_directory):
        print(f"오류: '{log_directory}' 디렉토리를 찾을 수 없습니다. 경로를 확인해주세요.")
    else:
        log_files = sorted([f for f in os.listdir(log_directory) if f.endswith(".log")])
        
        if not log_files:
            print(f"'{log_directory}' 디렉토리에 .log 파일이 없습니다.")
        else:
            print("분석할 로그 파일을 선택하세요 (예: 1,3,5 또는 all):")
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
                        print("잘못된 번호입니다. 목록에 있는 번호를 다시 입력하세요.")
                except ValueError:
                    print("숫자, 쉼표(,), 또는 'all'만 입력해주세요.")

            if selected_files:
                analyze_and_plot_logs(log_directory, selected_files)