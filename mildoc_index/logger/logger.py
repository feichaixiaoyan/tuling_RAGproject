import logging


def setup_logging(name:str="default",log_level=logging.INFO):
    """
    设置日志等级

    Args:
        log_level (int): The logging level to be set. Default is logging.INFO.
    """
    #配置根日志器的设置
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    #这个是拿到带名字的
    logger=logging.getLogger(name)
    
    return logger

if __name__ == "__main__":
    logger = setup_logging(log_level=logging.WARNING)

    logger.debug("调试信息")
    logger.info("开始处理")
    logger.warning("文件内容为空")
    logger.error("解析失败")